from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from codemind.agents.base import BaseAgent
from codemind.agents.budget_controller import BudgetControllerAgent
from codemind.agents.graph_builder import GraphBuilderAgent
from codemind.agents.graph_retrieval import GraphRetrievalAgent
from codemind.agents.impact_analysis import ImpactAnalysisAgent
from codemind.agents.lineage_builder import LineageBuilderAgent
from codemind.agents.llm_reasoning import LLMReasoningAgent
from codemind.agents.query_parser import QueryParserAgent
from codemind.agents.risk_scoring import RiskScoringAgent
from codemind.core.config import get_config
from codemind.core.models import (
    AgentInput,
    AgentOutput,
    Edge,
    Graph,
    Node,
    QueryIntent,
    RiskScore,
    TokenBudget,
)
from codemind.knowledge.embedding_index import EmbeddingIndex
from codemind.knowledge.neo4j_store import Neo4jStore


class Orchestrator:
    GRAPH_FILE = "graph.json"

    def __init__(self) -> None:
        self._config = get_config()
        self._query_parser = QueryParserAgent()
        self._graph_builder = GraphBuilderAgent()
        self._graph_retrieval = GraphRetrievalAgent()
        self._impact_analysis = ImpactAnalysisAgent()
        self._risk_scoring = RiskScoringAgent()
        self._lineage_builder = LineageBuilderAgent()
        self._llm_reasoning = LLMReasoningAgent()
        self._budget_controller = BudgetControllerAgent()

        self._graph: Optional[Graph] = None
        self._neo4j = Neo4jStore()
        self._embedding_index = EmbeddingIndex()

        self._graph_path = str(self._config.data_dir / self.GRAPH_FILE)
        self._try_load_assets()

    def _try_load_assets(self) -> None:
        if Path(self._graph_path).exists():
            try:
                self._graph = Graph.load(self._graph_path)
            except Exception:
                self._graph = None

        if self._graph is not None:
            try:
                if self._embedding_index.load_index():
                    pass
                else:
                    self._embedding_index.build_index(self._graph.nodes)
            except Exception:
                pass

    def _save_assets(self) -> None:
        if self._graph is not None:
            try:
                self._graph.save(self._graph_path)
            except Exception:
                pass

    def index_repository(self, repo_path: str, language: str = "sql") -> dict[str, Any]:
        start_time = time.time()

        builder_input = AgentInput(data={"repo_path": repo_path, "language": language})
        builder_output = self._graph_builder.run(builder_input)

        if not builder_output.success:
            return {
                "success": False,
                "error": builder_output.error,
                "elapsed_ms": (time.time() - start_time) * 1000,
            }

        graph_data = builder_output.data.get("graph", {})
        self._graph = Graph(
            nodes=[Node(**n) for n in graph_data.get("nodes", [])],
            edges=[Edge(**e) for e in graph_data.get("edges", [])],
        )

        self._save_assets()

        try:
            self._embedding_index.build_index(self._graph.nodes)
        except Exception:
            pass

        neo4j_stored = 0
        try:
            if self._neo4j.connect():
                self._neo4j.clear_all()
                neo4j_stored = self._neo4j.store_graph(self._graph)
                self._neo4j.close()
        except Exception:
            pass

        elapsed = (time.time() - start_time) * 1000

        return {
            "success": True,
            "node_count": self._graph.node_count(),
            "edge_count": self._graph.edge_count(),
            "token_estimate": self._graph.estimate_tokens(),
            "neo4j_stored": neo4j_stored,
            "embedding_indexed": self._graph.node_count(),
            "graph_saved_to": self._graph_path,
            "elapsed_ms": round(elapsed, 2),
        }

    def _resolve_intent(self, raw_intent: str) -> str:
        if isinstance(raw_intent, QueryIntent):
            return raw_intent.value
        return str(raw_intent)

    def _semantic_search_nodes(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        return self._embedding_index.search(query, top_k)

    def _neo4j_retrieve(self, node_id: str, max_depth: int = 3) -> Optional[Graph]:
        try:
            if self._neo4j.connect():
                result = self._neo4j.query_neighbors(node_id, max_depth)
                self._neo4j.close()
                if result.node_count() > 0:
                    return result
        except Exception:
            pass
        return None

    def query(self, user_query: str, budget: int = 0) -> dict[str, Any]:
        start_time = time.time()

        if not self._graph:
            return {
                "success": False,
                "error": "No graph loaded. Run index_repository first.",
                "elapsed_ms": (time.time() - start_time) * 1000,
            }

        budget = budget or self._config.token_budget_default

        parse_input = AgentInput(data={"query": user_query})
        parse_output = self._query_parser.run(parse_input)

        if not parse_output.success:
            return {
                "success": False,
                "error": f"Query parsing failed: {parse_output.error}",
                "elapsed_ms": (time.time() - start_time) * 1000,
            }

        intent = self._resolve_intent(parse_output.data.get("intent", "ARCHITECTURE_QA"))
        entities = parse_output.data.get("entities", [])
        constraints = parse_output.data.get("constraints", {})

        semantic_results = self._semantic_search_nodes(user_query, top_k=5)
        if semantic_results and entities:
            existing_ids = set()
            for entity in entities:
                for node in self._graph.nodes:
                    if entity.lower() in node.name.lower() or entity.lower() in (node.qualified_name or "").lower():
                        existing_ids.add(node.id)
            for node_id, score in semantic_results:
                if node_id not in existing_ids:
                    node = self._graph.get_node(node_id)
                    if node and node.name not in entities:
                        entities.append(node.name)

        budget_input = AgentInput(data={
            "graph_size": self._graph.node_count(),
            "edge_size": self._graph.edge_count(),
            "llm_required": True,
            "budget": budget,
        })
        budget_output = self._budget_controller.run(budget_input)
        budget_strategy = budget_output.data.get("strategy", "NORMAL")
        llm_allowed = budget_output.data.get("llm_tokens", 0) > 0

        retrieval_input = AgentInput(data={
            "graph": self._graph.model_dump(),
            "entities": entities,
            "intent": intent,
            "constraints": constraints,
        })
        retrieval_output = self._graph_retrieval.run(retrieval_input)

        if not retrieval_output.success:
            return {
                "success": False,
                "error": f"Graph retrieval failed: {retrieval_output.error}",
                "elapsed_ms": (time.time() - start_time) * 1000,
            }

        subgraph_data = retrieval_output.data.get("subgraph", {})

        result: dict[str, Any] = {
            "success": True,
            "query": user_query,
            "intent": intent,
            "entities": entities,
            "budget_strategy": budget_strategy,
            "subgraph": subgraph_data,
            "elapsed_ms": 0,
        }

        target = entities[0] if entities else ""

        if target and (intent == QueryIntent.IMPACT_ANALYSIS.value
                       or intent == "IMPACT_ANALYSIS"
                       or intent == QueryIntent.RISK_ASSESSMENT.value
                       or intent == "RISK_ASSESSMENT"):
            impact_input = AgentInput(data={
                "subgraph": subgraph_data,
                "target": target,
            })
            impact_output = self._impact_analysis.run(impact_input)

            if impact_output.success:
                result["impact"] = impact_output.data

                risk_input = AgentInput(data={
                    "impact_graph": impact_output.data,
                    "graph": subgraph_data,
                })
                risk_output = self._risk_scoring.run(risk_input)

                if risk_output.success:
                    result["risk"] = risk_output.data

        elif target and (intent == QueryIntent.LINEAGE_QUERY.value
                         or intent == "LINEAGE_QUERY"):
            lineage_sql = self._get_sql_for_entity(target)
            lineage_input = AgentInput(data={"sql": lineage_sql, "proc": target})
            lineage_output = self._lineage_builder.run(lineage_input)

            if lineage_output.success and lineage_output.data.get("lineage_edges"):
                result["lineage"] = lineage_output.data

            if target:
                impact_input = AgentInput(data={
                    "subgraph": subgraph_data,
                    "target": target,
                })
                impact_output = self._impact_analysis.run(impact_input)
                if impact_output.success:
                    result["impact"] = impact_output.data

                    risk_input = AgentInput(data={
                        "impact_graph": impact_output.data,
                        "graph": subgraph_data,
                    })
                    risk_output = self._risk_scoring.run(risk_input)
                    if risk_output.success:
                        result["risk"] = risk_output.data

        if llm_allowed and budget_strategy != "NO_LLM":
            llm_input = AgentInput(data={
                "graph": subgraph_data,
                "question": user_query,
                "context": self._build_context(result),
            })
            llm_output = self._llm_reasoning.run(llm_input)

            if llm_output.success:
                result["explanation"] = llm_output.data.get("explanation", "")
                result["llm_fallback"] = llm_output.data.get("fallback", False)

        result["elapsed_ms"] = round((time.time() - start_time) * 1000, 2)

        return result

    def get_graph_stats(self) -> dict[str, Any]:
        if not self._graph:
            return {"loaded": False}

        type_counts: dict[str, int] = {}
        for node in self._graph.nodes:
            type_counts[node.type.value] = type_counts.get(node.type.value, 0) + 1

        edge_type_counts: dict[str, int] = {}
        for edge in self._graph.edges:
            edge_type_counts[edge.type.value] = edge_type_counts.get(edge.type.value, 0) + 1

        return {
            "loaded": True,
            "node_count": self._graph.node_count(),
            "edge_count": self._graph.edge_count(),
            "token_estimate": self._graph.estimate_tokens(),
            "node_types": type_counts,
            "edge_types": edge_type_counts,
            "graph_path": self._graph_path,
            "embedding_available": self._embedding_index._embeddings is not None,
        }

    def _get_sql_for_entity(self, entity: str) -> str:
        if not self._graph:
            return ""
        for node in self._graph.nodes:
            if entity.lower() in node.name.lower():
                return node.source_code or ""
        return ""

    def _build_context(self, result: dict[str, Any]) -> str:
        parts: list[str] = []

        if "impact" in result:
            impact = result["impact"]
            parts.append(f"影响分析: 共影响 {impact.get('total_affected', 0)} 个节点, "
                         f"最大深度 {impact.get('max_depth', 0)}, "
                         f"平均置信度 {impact.get('avg_confidence', 0):.2f}")

        if "risk" in result:
            risk = result["risk"]
            parts.append(f"风险评分: {risk.get('score', 0)}/100, "
                         f"等级: {risk.get('level', 'UNKNOWN')}")

        if "lineage" in result:
            lineage = result["lineage"]
            parts.append(f"血缘关系: {lineage.get('lineage_count', 0)} 条")

        return "\n".join(parts)
