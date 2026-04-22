from __future__ import annotations

from typing import Any, Optional

from codemind.agents.base import BaseAgent
from codemind.core.config import get_config
from codemind.core.models import AgentInput, AgentOutput, Graph, Node, NodeType


class LLMReasoningAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__("LLMReasoning")
        self._config = get_config()
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self._config.openai_api_key,
                    base_url=self._config.openai_base_url,
                )
            except ImportError:
                raise RuntimeError("openai package is required for LLM reasoning")
        return self._client

    def _execute(self, agent_input: AgentInput) -> AgentOutput:
        graph_data = agent_input.data.get("graph", {})
        question = agent_input.data.get("question", "")
        context = agent_input.data.get("context", "")

        if not question:
            return AgentOutput(
                data={},
                success=False,
                error="No question provided",
            )

        graph_context = self._serialize_graph_context(graph_data)
        full_context = f"{context}\n\n{graph_context}" if context else graph_context

        try:
            explanation = self._call_llm(question, full_context)
            return AgentOutput(
                data={"explanation": explanation},
                confidence=0.8,
                success=True,
            )
        except Exception as e:
            fallback = self._generate_fallback_explanation(graph_data, question)
            return AgentOutput(
                data={"explanation": fallback, "fallback": True},
                confidence=0.5,
                success=True,
                error=str(e),
            )

    def _call_llm(self, question: str, context: str) -> str:
        client = self._get_client()

        system_prompt = """你是 Harness-DB-CodeMind 代码智能系统的解释引擎。
你的任务是基于代码图谱数据，为用户提供清晰、准确的解释。

规则：
1. 基于提供的图谱数据回答，不要编造信息
2. 如果数据不足以回答，明确说明
3. 使用结构化格式（列表、表格）提高可读性
4. 对于影响分析，说明传播路径和置信度
5. 对于血缘查询，说明数据流向和转换逻辑"""

        response = client.chat.completions.create(
            model=self._config.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"上下文数据:\n{context}\n\n问题: {question}"},
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        return response.choices[0].message.content or ""

    def _serialize_graph_context(self, graph_data: dict[str, Any]) -> str:
        if not graph_data:
            return "无图谱数据"

        parts: list[str] = []

        nodes = graph_data.get("nodes", [])
        if nodes:
            parts.append("=== 节点 ===")
            for n in nodes[:30]:
                node_type = n.get("type", "UNKNOWN")
                name = n.get("name", "")
                qualified = n.get("qualified_name", name)
                parts.append(f"  [{node_type}] {qualified}")

        edges = graph_data.get("edges", [])
        if edges:
            parts.append("=== 关系 ===")
            for e in edges[:30]:
                edge_type = e.get("type", "UNKNOWN")
                source = e.get("source_id", "")
                target = e.get("target_id", "")
                weight = e.get("weight", 1.0)
                parts.append(f"  {source} --[{edge_type}, w={weight}]--> {target}")

        impacts = graph_data.get("impacts", [])
        if impacts:
            parts.append("=== 影响分析 ===")
            for imp in impacts[:20]:
                name = imp.get("node_name", "")
                depth = imp.get("depth", 0)
                conf = imp.get("confidence", 0)
                parts.append(f"  {name} (深度={depth}, 置信度={conf:.2f})")

        lineage = graph_data.get("lineage_edges", [])
        if lineage:
            parts.append("=== 数据血缘 ===")
            for le in lineage[:20]:
                source = le.get("source", "")
                target = le.get("target", "")
                transform = le.get("transformation", "")
                parts.append(f"  {source} -> {target} [{transform}]")

        return "\n".join(parts)

    def _generate_fallback_explanation(self, graph_data: dict[str, Any], question: str) -> str:
        parts = ["[系统自动生成 - LLM不可用]"]

        nodes = graph_data.get("nodes", [])
        if nodes:
            parts.append(f"涉及 {len(nodes)} 个代码节点:")
            for n in nodes[:10]:
                parts.append(f"  - {n.get('type', '?')}: {n.get('name', '?')}")

        edges = graph_data.get("edges", [])
        if edges:
            parts.append(f"涉及 {len(edges)} 条关系边:")
            for e in edges[:10]:
                parts.append(f"  - {e.get('type', '?')}: {e.get('source_id', '?')} -> {e.get('target_id', '?')}")

        impacts = graph_data.get("impacts", [])
        if impacts:
            parts.append(f"影响范围: {len(impacts)} 个节点")
            for imp in impacts[:5]:
                parts.append(f"  - {imp.get('node_name', '?')} (深度={imp.get('depth', '?')}, 置信度={imp.get('confidence', '?')})")

        return "\n".join(parts)
