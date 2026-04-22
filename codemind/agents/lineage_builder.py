from __future__ import annotations

from typing import Any

from codemind.agents.base import BaseAgent
from codemind.core.models import AgentInput, AgentOutput, Edge, EdgeType, LineageEdge
from codemind.deterministic.sql_parser import SQLParser


class LineageBuilderAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("LineageBuilder")
        self._sql_parser = SQLParser()

    def _execute(self, agent_input: AgentInput) -> AgentOutput:
        sql = agent_input.data.get("sql", "")
        proc_name = agent_input.data.get("proc", "")

        if not sql:
            return AgentOutput(
                data={},
                success=False,
                error="No SQL provided",
            )

        if proc_name:
            statements = self._sql_parser.parse_procedure(sql, proc_name)
        else:
            statements = self._sql_parser.parse(sql)

        all_lineage: list[dict[str, Any]] = []
        for stmt in statements:
            for lineage_edge in stmt.column_lineage:
                all_lineage.append({
                    "source": lineage_edge.source,
                    "target": lineage_edge.target,
                    "transformation": lineage_edge.transformation,
                    "via": lineage_edge.via,
                    "stmt_type": stmt.stmt_type,
                    "procedure": stmt.procedure_name,
                })

        return AgentOutput(
            data={
                "lineage_edges": all_lineage,
                "statement_count": len(statements),
                "lineage_count": len(all_lineage),
            },
            confidence=1.0,
            success=True,
        )
