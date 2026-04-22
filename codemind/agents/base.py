from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from codemind.core.models import AgentInput, AgentOutput


class BaseAgent(ABC):
    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, agent_input: AgentInput) -> AgentOutput:
        start_time = time.time()
        try:
            result = self._execute(agent_input)
            latency = (time.time() - start_time) * 1000
            result.latency_ms = latency
            return result
        except Exception as e:
            latency = (time.time() - start_time) * 1000
            return AgentOutput(
                data={},
                latency_ms=latency,
                confidence=0.0,
                success=False,
                error=str(e),
            )

    @abstractmethod
    def _execute(self, agent_input: AgentInput) -> AgentOutput:
        ...
