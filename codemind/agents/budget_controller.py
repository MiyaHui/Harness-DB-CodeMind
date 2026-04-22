from __future__ import annotations

from typing import Any

from codemind.agents.base import BaseAgent
from codemind.core.config import get_config
from codemind.core.models import AgentInput, AgentOutput, TokenBudget


class BudgetControllerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("BudgetController")
        self._config = get_config()

    def _execute(self, agent_input: AgentInput) -> AgentOutput:
        graph_size = agent_input.data.get("graph_size", 0)
        edge_size = agent_input.data.get("edge_size", 0)
        llm_required = agent_input.data.get("llm_required", False)
        budget_limit = agent_input.data.get("budget", self._config.token_budget_default)

        budget = TokenBudget(total_budget=budget_limit)

        graph_tokens = graph_size * 25 + edge_size * 10
        llm_tokens = 2000 if llm_required else 0

        allowed = budget.allocate(graph_tokens, llm_tokens)

        strategy = "NORMAL"
        if not allowed:
            strategy = budget.degrade()
            while budget.exceeded and budget.strategy != "MINIMAL":
                strategy = budget.degrade()

        return AgentOutput(
            data={
                "allowed": budget.used <= budget.total_budget,
                "strategy": strategy,
                "budget": budget.model_dump(),
                "graph_tokens": budget.graph_tokens,
                "llm_tokens": budget.llm_tokens,
                "total_used": budget.used,
                "remaining": budget.remaining,
            },
            confidence=1.0,
            success=True,
        )
