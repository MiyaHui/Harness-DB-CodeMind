from __future__ import annotations

import os
import time
from typing import Any

from codemind.agents.base import BaseAgent
from codemind.core.models import AgentInput, AgentOutput, Graph, NodeType
from codemind.deterministic.cpg_builder import CPGBuilder
from codemind.deterministic.git_analyzer import GitAnalyzer


class GraphBuilderAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("GraphBuilder")
        self._cpg_builder = CPGBuilder()

    def _execute(self, agent_input: AgentInput) -> AgentOutput:
        repo_path = agent_input.data.get("repo_path", "")
        language = agent_input.data.get("language", "sql")

        if not repo_path or not os.path.exists(repo_path):
            return AgentOutput(
                data={},
                success=False,
                error=f"Repository path not found: {repo_path}",
            )

        graph = self._build_graph(repo_path, language)

        change_frequency: dict[str, int] = {}
        if os.path.isdir(os.path.join(repo_path, ".git")):
            try:
                git_analyzer = GitAnalyzer(repo_path)
                change_frequency = git_analyzer.get_change_frequency()
            except Exception:
                pass

        for node in graph.nodes:
            if node.file_path in change_frequency:
                node.metadata["change_frequency"] = change_frequency[node.file_path]

        return AgentOutput(
            data={
                "graph": graph.model_dump(),
                "node_count": graph.node_count(),
                "edge_count": graph.edge_count(),
                "token_estimate": graph.estimate_tokens(),
            },
            confidence=1.0,
            success=True,
        )

    def _build_graph(self, repo_path: str, language: str) -> Graph:
        if os.path.isfile(repo_path):
            if repo_path.endswith(".sql"):
                return self._cpg_builder.build_from_sql_file(repo_path)
            elif repo_path.endswith(".java"):
                return self._cpg_builder.build_from_java_file(repo_path)
            elif repo_path.endswith(".py"):
                return self._cpg_builder.build_from_python_file(repo_path)
            else:
                return Graph()
        else:
            return self._cpg_builder.build_from_directory(repo_path)
