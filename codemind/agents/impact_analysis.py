from __future__ import annotations

from collections import deque
from typing import Any

from codemind.agents.base import BaseAgent
from codemind.core.config import get_config
from codemind.core.models import (
    AgentInput,
    AgentOutput,
    Edge,
    EdgeType,
    Graph,
    ImpactNode,
    ImpactResult,
    Node,
    NodeType,
)


class ImpactAnalysisAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("ImpactAnalysis")
        self._config = get_config()

    def _execute(self, agent_input: AgentInput) -> AgentOutput:
        graph_data = agent_input.data.get("subgraph", agent_input.data.get("graph", {}))
        target = agent_input.data.get("target", "")
        max_depth = agent_input.data.get("max_depth", self._config.impact_max_depth)
        confidence_threshold = agent_input.data.get(
            "confidence_threshold", self._config.impact_confidence_threshold
        )

        graph = self._reconstruct_graph(graph_data)
        if not graph.nodes:
            return AgentOutput(
                data={},
                success=False,
                error="Empty graph for impact analysis",
            )

        target_node = self._find_target(graph, target)
        if not target_node:
            return AgentOutput(
                data={},
                success=False,
                error=f"Target not found: {target}",
            )

        impact_result = self._propagate_impact(
            graph, target_node, max_depth, confidence_threshold
        )

        return AgentOutput(
            data=impact_result.model_dump(),
            confidence=impact_result.avg_confidence,
            success=True,
        )

    def _reconstruct_graph(self, graph_data: dict[str, Any]) -> Graph:
        if not graph_data:
            return Graph()
        nodes = [Node(**n) for n in graph_data.get("nodes", [])]
        edges = [Edge(**e) for e in graph_data.get("edges", [])]
        return Graph(nodes=nodes, edges=edges)

    def _find_target(self, graph: Graph, target: str) -> Node | None:
        node = graph.get_node_by_name(target)
        if node:
            return node

        for n in graph.nodes:
            if target.lower() in n.name.lower():
                return n
            if n.qualified_name and target.lower() in n.qualified_name.lower():
                return n

        target_clean = target.replace(".", "_").lower()
        for n in graph.nodes:
            if n.id.endswith(target_clean):
                return n

        return None

    def _propagate_impact(
        self,
        graph: Graph,
        target: Node,
        max_depth: int,
        threshold: float,
    ) -> ImpactResult:
        impacts: list[ImpactNode] = []
        visited: dict[str, float] = {target.id: 1.0}

        queue: deque[tuple[str, int, float, list[str]]] = deque()
        queue.append((target.id, 0, 1.0, [target.name]))

        while queue:
            current_id, depth, confidence, path = queue.popleft()

            if depth > max_depth:
                continue

            current_node = graph.get_node(current_id)
            if not current_node:
                continue

            if depth > 0:
                impacts.append(ImpactNode(
                    node_id=current_id,
                    node_name=current_node.name,
                    node_type=current_node.type,
                    depth=depth,
                    confidence=round(confidence, 4),
                    path=path,
                ))

            for edge in graph.get_outgoing_edges(current_id):
                edge_weight = self._compute_edge_weight(edge)
                new_confidence = confidence * edge_weight

                if new_confidence < threshold:
                    continue

                if edge.target_id in visited and visited[edge.target_id] >= new_confidence:
                    continue

                visited[edge.target_id] = new_confidence
                target_node = graph.get_node(edge.target_id)
                new_path = path + [target_node.name if target_node else edge.target_id]
                queue.append((edge.target_id, depth + 1, new_confidence, new_path))

            for edge in graph.get_incoming_edges(current_id):
                if edge.type in (EdgeType.CONTAINS,):
                    continue

                edge_weight = self._compute_edge_weight(edge)
                new_confidence = confidence * edge_weight * 0.8

                if new_confidence < threshold:
                    continue

                if edge.source_id in visited and visited[edge.source_id] >= new_confidence:
                    continue

                visited[edge.source_id] = new_confidence
                source_node = graph.get_node(edge.source_id)
                new_path = path + [source_node.name if source_node else edge.source_id]
                queue.append((edge.source_id, depth + 1, new_confidence, new_path))

        total_affected = len(impacts)
        max_impact_depth = max((i.depth for i in impacts), default=0)
        avg_confidence = (
            sum(i.confidence for i in impacts) / len(impacts) if impacts else 0.0
        )

        return ImpactResult(
            target=target.name,
            impacts=sorted(impacts, key=lambda x: (x.depth, -x.confidence)),
            total_affected=total_affected,
            max_depth=max_impact_depth,
            avg_confidence=round(avg_confidence, 4),
        )

    def _compute_edge_weight(self, edge: Edge) -> float:
        base_weight = edge.weight

        type_weights = {
            EdgeType.CALL: 0.9,
            EdgeType.WRITE: 0.85,
            EdgeType.READ: 0.7,
            EdgeType.LINEAGE: 0.95,
            EdgeType.REFERENCES: 0.6,
            EdgeType.DERIVES_FROM: 0.8,
            EdgeType.CONTAINS: 0.3,
            EdgeType.IMPORTS: 0.5,
        }

        type_weight = type_weights.get(edge.type, 0.5)
        return base_weight * type_weight
