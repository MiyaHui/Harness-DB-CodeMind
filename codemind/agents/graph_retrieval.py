from __future__ import annotations

from typing import Any, Optional

from codemind.agents.base import BaseAgent
from codemind.core.models import AgentInput, AgentOutput, Edge, EdgeType, Graph, Node, NodeType


class GraphRetrievalAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("GraphRetrieval")

    def _execute(self, agent_input: AgentInput) -> AgentOutput:
        graph_data = agent_input.data.get("graph", {})
        entities = agent_input.data.get("entities", [])
        intent = agent_input.data.get("intent", "IMPACT_ANALYSIS")
        max_depth = agent_input.data.get("constraints", {}).get("depth", 3)
        max_nodes = agent_input.data.get("constraints", {}).get("max_nodes", 100)

        graph = self._reconstruct_graph(graph_data)
        if not graph.nodes:
            return AgentOutput(
                data={"subgraph": Graph().model_dump()},
                success=False,
                error="Empty graph provided",
            )

        seed_nodes = self._resolve_seed_nodes(graph, entities)
        if not seed_nodes:
            seed_nodes = self._fuzzy_match_nodes(graph, entities)

        if not seed_nodes:
            return AgentOutput(
                data={"subgraph": Graph().model_dump(), "seed_nodes": []},
                success=False,
                error=f"Could not find nodes matching: {entities}",
            )

        subgraph = self._retrieve_subgraph(graph, seed_nodes, intent, max_depth, max_nodes)
        ranked_nodes = self._rank_nodes(subgraph, seed_nodes)

        return AgentOutput(
            data={
                "subgraph": subgraph.model_dump(),
                "seed_nodes": [n.id for n in seed_nodes],
                "ranked_nodes": ranked_nodes,
                "node_count": subgraph.node_count(),
                "edge_count": subgraph.edge_count(),
                "token_estimate": subgraph.estimate_tokens(),
            },
            confidence=0.85,
            success=True,
        )

    def _reconstruct_graph(self, graph_data: dict[str, Any]) -> Graph:
        if not graph_data:
            return Graph()

        nodes = []
        for n in graph_data.get("nodes", []):
            nodes.append(Node(**n))

        edges = []
        for e in graph_data.get("edges", []):
            edges.append(Edge(**e))

        return Graph(nodes=nodes, edges=edges)

    def _resolve_seed_nodes(self, graph: Graph, entities: list[str]) -> list[Node]:
        seed_nodes: list[Node] = []

        for entity in entities:
            node = graph.get_node_by_name(entity)
            if node:
                seed_nodes.append(node)
                continue

            for n in graph.nodes:
                if entity.lower() in n.name.lower() or entity.lower() in n.qualified_name.lower():
                    seed_nodes.append(n)
                    break

            if not any(n.name == entity for n in seed_nodes):
                for n in graph.nodes:
                    if n.type == NodeType.COLUMN and entity.lower() in n.qualified_name.lower():
                        seed_nodes.append(n)
                        break

        return seed_nodes

    def _fuzzy_match_nodes(self, graph: Graph, entities: list[str]) -> list[Node]:
        matched: list[Node] = []
        for entity in entities:
            parts = entity.replace(".", " ").replace("_", " ").lower().split()
            best_node: Optional[Node] = None
            best_score = 0.0

            for node in graph.nodes:
                score = 0.0
                node_parts = node.name.replace("_", " ").lower().split()
                for ep in parts:
                    for np in node_parts:
                        if ep == np:
                            score += 2.0
                        elif ep in np or np in ep:
                            score += 1.0

                if node.qualified_name:
                    qn_parts = node.qualified_name.replace(".", " ").replace("_", " ").lower().split()
                    for ep in parts:
                        for qp in qn_parts:
                            if ep == qp:
                                score += 2.0
                            elif ep in qp or qp in ep:
                                score += 1.0

                if score > best_score:
                    best_score = score
                    best_node = node

            if best_node and best_score > 0:
                matched.append(best_node)

        return matched

    def _retrieve_subgraph(self, graph: Graph, seed_nodes: list[Node],
                            intent: str, max_depth: int, max_nodes: int) -> Graph:
        visited: set[str] = set()
        result_nodes: list[Node] = []
        result_edges: list[Edge] = []

        queue: list[tuple[str, int]] = []
        for sn in seed_nodes:
            queue.append((sn.id, 0))
            visited.add(sn.id)

        while queue:
            current_id, depth = queue.pop(0)

            if len(result_nodes) >= max_nodes:
                break

            node = graph.get_node(current_id)
            if node:
                result_nodes.append(node)

            if depth >= max_depth:
                continue

            edge_types = self._get_relevant_edge_types(intent)

            for edge in graph.get_outgoing_edges(current_id):
                if edge.type in edge_types or not edge_types:
                    result_edges.append(edge)
                    if edge.target_id not in visited:
                        visited.add(edge.target_id)
                        queue.append((edge.target_id, depth + 1))

            for edge in graph.get_incoming_edges(current_id):
                if edge.type in edge_types or not edge_types:
                    result_edges.append(edge)
                    if edge.source_id not in visited:
                        visited.add(edge.source_id)
                        queue.append((edge.source_id, depth + 1))

        return Graph(nodes=result_nodes, edges=result_edges)

    def _get_relevant_edge_types(self, intent: str) -> list[EdgeType]:
        from codemind.core.models import QueryIntent

        intent_map = {
            QueryIntent.IMPACT_ANALYSIS: [EdgeType.CALL, EdgeType.WRITE, EdgeType.READ, EdgeType.LINEAGE],
            QueryIntent.LINEAGE_QUERY: [EdgeType.LINEAGE, EdgeType.READ, EdgeType.WRITE],
            QueryIntent.DEPENDENCY_QUERY: [EdgeType.CALL, EdgeType.IMPORTS, EdgeType.REFERENCES],
            QueryIntent.ARCHITECTURE_QA: [EdgeType.CALL, EdgeType.CONTAINS, EdgeType.READ, EdgeType.WRITE],
        }

        try:
            intent_enum = QueryIntent(intent)
            return intent_map.get(intent_enum, [])
        except ValueError:
            return []

    def _rank_nodes(self, subgraph: Graph, seed_nodes: list[Node]) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        seed_ids = {n.id for n in seed_nodes}

        for node in subgraph.nodes:
            out_degree = len(subgraph.get_outgoing_edges(node.id))
            in_degree = len(subgraph.get_incoming_edges(node.id))
            centrality = out_degree + in_degree

            is_seed = node.id in seed_ids
            score = centrality * (2.0 if is_seed else 1.0)

            if node.metadata.get("change_frequency"):
                score += node.metadata["change_frequency"] * 0.5

            ranked.append({
                "node_id": node.id,
                "name": node.name,
                "type": node.type.value,
                "score": round(score, 2),
                "is_seed": is_seed,
                "centrality": centrality,
            })

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:50]
