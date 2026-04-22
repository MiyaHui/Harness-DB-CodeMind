from __future__ import annotations

from typing import Any

from codemind.agents.base import BaseAgent
from codemind.core.config import get_config
from codemind.core.models import (
    AgentInput,
    AgentOutput,
    Edge,
    EdgeType,
    Graph,
    ImpactResult,
    ImpactNode,
    NodeType,
    RiskLevel,
    RiskScore,
)


class RiskScoringAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("RiskScoring")
        self._config = get_config()

    def _execute(self, agent_input: AgentInput) -> AgentOutput:
        impact_data = agent_input.data.get("impact_graph", agent_input.data.get("impact_result", {}))
        graph_data = agent_input.data.get("graph", {})

        if not impact_data:
            return AgentOutput(
                data={},
                success=False,
                error="No impact data provided for risk scoring",
            )

        impact_result = ImpactResult(**impact_data) if isinstance(impact_data, dict) else impact_data

        graph = self._reconstruct_graph(graph_data) if graph_data else Graph()

        risk_score = self._compute_risk(impact_result, graph)

        return AgentOutput(
            data=risk_score.model_dump(),
            confidence=0.85,
            success=True,
        )

    def _reconstruct_graph(self, graph_data: dict[str, Any]) -> Graph:
        from codemind.core.models import Node, Edge
        nodes = [Node(**n) for n in graph_data.get("nodes", [])]
        edges = [Edge(**e) for e in graph_data.get("edges", [])]
        return Graph(nodes=nodes, edges=edges)

    def _compute_risk(self, impact: ImpactResult, graph: Graph) -> RiskScore:
        weights = self._config.get_risk_weights()

        blast_radius = self._compute_blast_radius(impact)
        critical_path = self._compute_critical_path(impact)
        data_sensitivity = self._compute_data_sensitivity(impact)
        change_frequency = self._compute_change_frequency(impact, graph)
        coupling = self._compute_coupling(impact, graph)
        test_coverage = self._compute_test_coverage(impact, graph)

        factors = {
            "blast_radius": blast_radius,
            "critical_path": critical_path,
            "data_sensitivity": data_sensitivity,
            "change_frequency": change_frequency,
            "coupling": coupling,
            "test_coverage": test_coverage,
        }

        score = sum(
            weights.get(factor, 0) * value
            for factor, value in factors.items()
        )

        score = min(100, max(0, score * 100))

        level = self._determine_risk_level(score)

        explanation = self._generate_explanation(factors, score, level)

        return RiskScore(
            score=round(score, 1),
            level=level,
            factors={k: round(v, 3) for k, v in factors.items()},
            explanation=explanation,
        )

    def _compute_blast_radius(self, impact: ImpactResult) -> float:
        if impact.total_affected == 0:
            return 0.0
        normalized = min(1.0, impact.total_affected / 20.0)
        depth_factor = min(1.0, impact.max_depth / 5.0)
        return (normalized * 0.7 + depth_factor * 0.3)

    def _compute_critical_path(self, impact: ImpactResult) -> float:
        critical_types = {NodeType.PROCEDURE, NodeType.FUNCTION, NodeType.TABLE}
        critical_count = sum(
            1 for i in impact.impacts if i.node_type in critical_types
        )
        if impact.total_affected == 0:
            return 0.0
        ratio = critical_count / max(1, impact.total_affected)
        return min(1.0, ratio)

    def _compute_data_sensitivity(self, impact: ImpactResult) -> float:
        sensitive_keywords = {
            "password", "secret", "token", "credit", "ssn", "salary",
            "amount", "balance", "payment", "invoice", "order", "account",
        }
        sensitive_count = 0
        for imp in impact.impacts:
            name_lower = imp.node_name.lower()
            if any(kw in name_lower for kw in sensitive_keywords):
                sensitive_count += 1

        if impact.total_affected == 0:
            return 0.0
        ratio = sensitive_count / max(1, impact.total_affected)
        return min(1.0, ratio * 2)

    def _compute_change_frequency(self, impact: ImpactResult, graph: Graph) -> float:
        freq_values: list[int] = []
        for imp in impact.impacts:
            node = graph.get_node(imp.node_id)
            if node and node.metadata.get("change_frequency"):
                freq_values.append(node.metadata["change_frequency"])

        if not freq_values:
            return 0.5

        avg_freq = sum(freq_values) / len(freq_values)
        return min(1.0, avg_freq / 10.0)

    def _compute_coupling(self, impact: ImpactResult, graph: Graph) -> float:
        total_edges = 0
        for imp in impact.impacts:
            out = len(graph.get_outgoing_edges(imp.node_id))
            inc = len(graph.get_incoming_edges(imp.node_id))
            total_edges += out + inc

        if impact.total_affected == 0:
            return 0.0
        avg_edges = total_edges / max(1, impact.total_affected)
        return min(1.0, avg_edges / 10.0)

    def _compute_test_coverage(self, impact: ImpactResult, graph: Graph) -> float:
        test_count = 0
        for imp in impact.impacts:
            node = graph.get_node(imp.node_id)
            if node and node.metadata.get("has_tests"):
                test_count += 1

        if impact.total_affected == 0:
            return 0.5

        coverage = test_count / max(1, impact.total_affected)
        return 1.0 - coverage

    def _determine_risk_level(self, score: float) -> RiskLevel:
        if score >= 75:
            return RiskLevel.CRITICAL
        elif score >= 55:
            return RiskLevel.HIGH
        elif score >= 30:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _generate_explanation(self, factors: dict[str, float], score: float,
                               level: RiskLevel) -> str:
        parts = [f"风险等级: {level.value} (评分: {score:.1f}/100)"]

        high_factors = [(k, v) for k, v in factors.items() if v > 0.6]
        if high_factors:
            parts.append("主要风险因素:")
            factor_names = {
                "blast_radius": "影响范围广",
                "critical_path": "涉及核心链路",
                "data_sensitivity": "涉及敏感数据",
                "change_frequency": "变更频率高",
                "coupling": "耦合度高",
                "test_coverage": "测试覆盖不足",
            }
            for k, v in sorted(high_factors, key=lambda x: x[1], reverse=True):
                name = factor_names.get(k, k)
                parts.append(f"  - {name}: {v:.1%}")

        return "\n".join(parts)
