from __future__ import annotations

import re
from typing import Any

from codemind.agents.base import BaseAgent
from codemind.core.models import AgentInput, AgentOutput, ParsedQuery, QueryIntent


class QueryParserAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("QueryParser")
        self._intent_patterns: dict[QueryIntent, list[str]] = {
            QueryIntent.IMPACT_ANALYSIS: [
                r"修改\s*(.+?)\s*会影响",
                r"变更\s*(.+?)\s*的影响",
                r"改动\s*(.+?)\s*会",
                r"impact\s+of\s+changing\s+(.+)",
                r"what\s+.*affect.*\s+(.+)",
                r"what\s+happens.*change\s+(.+)",
                r"影响分析",
                r"影响范围",
            ],
            QueryIntent.LINEAGE_QUERY: [
                r"(.+?)\s*的来源",
                r"(.+?)\s*从哪",
                r"(.+?)\s*的血缘",
                r"lineage\s+of\s+(.+)",
                r"where\s+does\s+(.+)\s+come",
                r"data\s+flow.*(.+)",
                r"数据流向",
                r"数据来源",
            ],
            QueryIntent.ARCHITECTURE_QA: [
                r"(.+?)\s*是做什么",
                r"(.+?)\s*的功能",
                r"what\s+does\s+(.+)\s+do",
                r"explain\s+(.+)",
                r"架构",
                r"系统结构",
            ],
            QueryIntent.RISK_ASSESSMENT: [
                r"(.+?)\s*的风险",
                r"修改\s*(.+?)\s*风险",
                r"risk\s+of\s+(.+)",
                r"how\s+risky.*(.+)",
                r"风险评估",
            ],
            QueryIntent.REFACTOR_SUGGESTION: [
                r"重构\s*(.+)",
                r"refactor\s+(.+)",
                r"优化\s*(.+)",
                r"改进\s*(.+)",
            ],
            QueryIntent.DEPENDENCY_QUERY: [
                r"(.+?)\s*依赖",
                r"(.+?)\s*调用了什么",
                r"who\s+calls\s+(.+)",
                r"dependenc.*(.+)",
                r"调用关系",
            ],
        }
        self._entity_patterns = [
            r'(\w+\.\w+)',
            r'(\w+_\w+)',
            r'(sp_\w+)',
            r'(fn_\w+)',
            r'(proc_\w+)',
            r'(tbl_\w+)',
            r'(table_\w+)',
            r'(\w+)',
        ]

    def _execute(self, agent_input: AgentInput) -> AgentOutput:
        query = agent_input.data.get("query", "")
        if not query:
            return AgentOutput(
                data={},
                success=False,
                error="No query provided",
            )

        intent = self._detect_intent(query)
        entities = self._extract_entities(query)
        constraints = self._extract_constraints(query)

        parsed = ParsedQuery(
            intent=intent,
            entities=entities,
            constraints=constraints,
            original_query=query,
        )

        return AgentOutput(
            data=parsed.model_dump(),
            confidence=0.9 if intent != QueryIntent.ARCHITECTURE_QA else 0.7,
            success=True,
        )

    def _detect_intent(self, query: str) -> QueryIntent:
        query_lower = query.lower().strip()

        for intent, patterns in self._intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    return intent

        if any(kw in query_lower for kw in ["修改", "变更", "change", "modify", "alter"]):
            return QueryIntent.IMPACT_ANALYSIS
        if any(kw in query_lower for kw in ["血缘", "来源", "lineage", "flow"]):
            return QueryIntent.LINEAGE_QUERY
        if any(kw in query_lower for kw in ["风险", "risk"]):
            return QueryIntent.RISK_ASSESSMENT
        if any(kw in query_lower for kw in ["重构", "refactor"]):
            return QueryIntent.REFRACTOR_SUGGESTION
        if any(kw in query_lower for kw in ["依赖", "调用", "depend", "call"]):
            return QueryIntent.DEPENDENCY_QUERY

        return QueryIntent.ARCHITECTURE_QA

    def _extract_entities(self, query: str) -> list[str]:
        entities: list[str] = []

        for intent, patterns in self._intent_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match and match.groups():
                    entity = match.group(1).strip()
                    if entity and entity not in entities:
                        entities.append(entity)

        if not entities:
            for pattern in self._entity_patterns:
                matches = re.findall(pattern, query)
                for m in matches:
                    m = m.strip()
                    if m and len(m) > 1 and m.lower() not in {
                        "the", "is", "are", "was", "were", "what", "how",
                        "的", "了", "是", "在", "会", "有", "和", "与",
                    }:
                        if m not in entities:
                            entities.append(m)
                if entities:
                    break

        return entities[:10]

    def _extract_constraints(self, query: str) -> dict[str, Any]:
        constraints: dict[str, Any] = {}

        depth_match = re.search(r'深度\s*(\d+)|depth\s*(\d+)', query, re.IGNORECASE)
        if depth_match:
            constraints["depth"] = int(depth_match.group(1) or depth_match.group(2))

        limit_match = re.search(r'前\s*(\d+)|top\s*(\d+)|limit\s*(\d+)', query, re.IGNORECASE)
        if limit_match:
            constraints["limit"] = int(limit_match.group(1) or limit_match.group(2) or limit_match.group(3))

        if not constraints.get("depth"):
            constraints["depth"] = 3

        return constraints
