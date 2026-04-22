

:::writing{variant=“standard” id=“84291”}

Harness-DB-CodeMind

企业级 AI 代码智能中枢（Code Intelligence Infrastructure）

⸻

一、产品愿景（Vision）

构建一个可计算、可解释、可控成本的代码智能系统，将企业存量代码（尤其是存储过程）从：

❌ 黑盒文本 → ✅ 可查询的图结构资产

最终形态：

Codebase Digital Twin（代码数字孪生系统）

⸻

二、产品目标（Goals）

核心目标
	1.	代码结构数字化
	•	将代码转换为图（CPG + Lineage + Call Graph）
	2.	Token成本可控
	•	LLM仅参与“不可计算部分”
	•	可预测 Token 消耗
	3.	影响分析能力
	•	任意字段/函数变更 → 自动推导影响范围
	4.	风险量化能力
	•	输出风险评分（可用于发布决策）

⸻

业务价值
	•	降低重构风险
	•	提升系统可维护性
	•	让存量系统“可理解”
	•	提供变更决策支持（DevOps升级）

⸻

三、核心理念（Design Principles）

⸻

1️⃣ Code as Graph（代码即图谱）
	•	不直接使用全文RAG
	•	使用：
	•	Code Property Graph（CPG）
	•	Data Lineage Graph
	•	Call Graph

⸻

2️⃣ Neuro-Symbolic 架构

Deterministic Engine（图/规则）
+ LLM（语义解释）


⸻

3️⃣ Harness 三层控制

解析层 → 稀疏检索层 → 推理层


⸻

4️⃣ Token预算可控
	•	每次查询都有预算
	•	超预算自动降级

⸻

四、总体架构

Application Layer
  ├── 架构问答
  ├── 影响分析
  ├── 重构建议

Harness Orchestrator（核心）
  ├── Query Parser
  ├── Graph Retrieval Engine
  ├── Budget Controller
  ├── Reasoning Router

Hybrid Knowledge Layer
  ├── Code Property Graph (CPG)
  ├── Data Lineage Graph
  ├── Runtime Trace Graph
  ├── Business Ontology
  ├── Embedding Index

Deterministic Layer
  ├── Joern / CodeQL
  ├── SQL AST Parser（ANTLR）
  ├── Program Slicing
  ├── Git Analyzer


⸻

五、核心数据模型

⸻

1️⃣ 统一图模型

{
  "node": {
    "id": "func_123",
    "type": "FUNCTION | TABLE | COLUMN",
    "name": "sp_order_pay"
  },
  "edge": {
    "type": "CALL | READ | WRITE | LINEAGE"
  }
}


⸻

2️⃣ Data Lineage

{
  "source": "order.amount",
  "target": "invoice.total_amount",
  "transformation": "SUM",
  "via": "sp_generate_invoice"
}


⸻

3️⃣ Business Ontology

{
  "entity": "订单",
  "mapped_fields": ["order_id"],
  "tags": ["交易"]
}


⸻

六、核心引擎设计

⸻

6.1 Query-aware Graph Retrieval

⸻

核心流程

query → intent解析 → seed nodes
      → graph traversal + embedding检索
      → ranking
      → 子图压缩


⸻

评分函数

Score = α * 语义相似度
      + β * 图距离
      + γ * 变更频率
      + δ * 中心性


⸻

Neo4j实现（核心）

CALL apoc.path.expandConfig(start, {
  relationshipFilter: "CALL|READ|WRITE|LINEAGE",
  maxLevel: 3
})


⸻

6.2 Data Lineage Graph（SQL → 血缘）

⸻

支持语法
	•	SELECT / INSERT / UPDATE / MERGE
	•	JOIN / 子查询 / 聚合 / CASE

⸻

核心规则

SELECT

a.amount + b.tax → target

→

a.amount → target
b.tax → target


⸻

INSERT

INSERT INTO t (c1) SELECT a FROM s

→

s.a → t.c1


⸻

UPDATE

UPDATE t SET c = a + b

→

a → t.c
b → t.c


⸻

CASE WHEN

CASE WHEN a THEN b ELSE c

→

a, b, c → target


⸻

6.3 Impact Propagation（影响传播）

⸻

算法

BFS + confidence衰减


⸻

核心逻辑

new_conf = parent_conf × edge_weight


⸻

Neo4j实现

reduce(conf = 1.0, r IN relationships(path) | conf * r.weight)


⸻

6.4 Impact Risk Scoring（风险评分）

⸻

核心公式

Risk = \sum_{i=1}^{n} w_i \cdot f_i

⸻

风险因子

因子	说明
Blast Radius	影响范围
Critical Path	是否核心链路
Data Sensitivity	数据敏感度
Change Frequency	变更频率
Coupling	耦合度
Test Coverage	测试覆盖


⸻

示例评分

{
  "risk_score": 78,
  "level": "HIGH"
}


⸻

七、Token成本控制

⸻

估算模型

Token = 节点数 × 25 + 边数 × 10


⸻

降级策略

超预算 →
  减少graph depth
  降低节点数
  禁用LLM


⸻

八、执行流程（端到端）

⸻


用户提问
 → Query Parsing
 → Graph Retrieval
 → Impact Analysis
 → Risk Scoring
 → LLM解释（可选）
 → 返回结果


⸻

九、实施路线（6个月）

⸻

Phase 1（0 Token）
	•	CPG构建
	•	SQL解析
	•	图数据库

⸻

Phase 2
	•	Data Lineage
	•	Embedding
	•	Ontology

⸻

Phase 3
	•	Retrieval Engine
	•	Impact Propagation

⸻

Phase 4
	•	Risk Scoring
	•	LLM接入
	•	UI + API

⸻

十、系统边界与优势

⸻

相比传统RAG

能力	RAG	本系统
结构理解	❌	✅
成本控制	❌	✅
影响分析	❌	✅
风险评估	❌	✅


⸻

十一、最终定位

⸻

这不是一个：
	•	代码助手 ❌
	•	Copilot ❌

而是：

Code Intelligence Infrastructure（代码智能基础设施）

⸻

十二、下一步扩展（Roadmap）

⸻

	1.	Change Decision Engine（发布门禁）
	2.	自动重构建议
	3.	自学习权重（基于历史事故）
	4.	Runtime + 静态融合分析
	5.	多仓库跨系统分析

⸻

结论

Harness-DB-CodeMind 的核心价值在于：

将 AI 从“文本生成工具”，转变为“可计算的工程系统组件”。

最终实现：
	•	可解释
	•	可控成本
	•	可用于生产决策

⸻

:::

⸻

下面给你的是一份可直接驱动开发的多Agent协作蓝图（Production-grade）。重点不是概念，而是：
	•	Agent职责边界（避免耦合）
	•	输入 / 输出契约（可并行开发）
	•	调度协议（Orchestrator如何调用）
	•	失败 / 降级策略（保证系统可用性）

⸻

一、总体设计：Agent = 可替换的能力模块

Orchestrator（调度）
   ↓
[Graph Builder Agents]（离线）
[Query Agents]（在线）
[Reasoning Agents]（在线）
[Governance Agents]（控制）


⸻

二、Agent总览（建议最小可行集合）

Agent	类型	是否核心
Graph Builder Agent	离线	✅
Lineage Builder Agent	离线	✅
Query Parser Agent	在线	✅
Graph Retrieval Agent	在线	✅
Impact Analysis Agent	在线	✅
Risk Scoring Agent	在线	✅
LLM Reasoning Agent	在线	可选
Budget Controller Agent	在线	✅


⸻

三、Agent详细设计（可直接开发）

⸻

1️⃣ Graph Builder Agent（代码图构建）

⸻

职责
	•	构建 CPG（函数/调用关系）
	•	构建基础节点（TABLE / COLUMN / PROCEDURE）

⸻

输入

{
  "repo_path": "/codebase",
  "language": "java/sql"
}


⸻

输出（写入Neo4j）

{
  "nodes": [...],
  "edges": [...]
}


⸻

核心逻辑

run_joern()
extract_functions()
extract_call_graph()
store_to_graph()


⸻

调度

每天夜间批处理


⸻

2️⃣ Lineage Builder Agent（SQL血缘）

⸻

职责
	•	解析 SQL AST
	•	构建 COLUMN级血缘

⸻

输入

{
  "sql": "SELECT a.amount FROM order a",
  "proc": "sp_order"
}


⸻

输出

{
  "lineage_edges": [
    {"source": "order.amount", "target": "result"}
  ]
}


⸻

核心能力
	•	JOIN / CASE / 聚合
	•	UPDATE / INSERT / MERGE

⸻

调度

代码变更触发 or 定时


⸻

3️⃣ Query Parser Agent（查询解析）

⸻

职责
	•	将自然语言转为结构化Query

⸻

输入

“修改 order.amount 会影响什么？”


⸻

输出

{
  "intent": "IMPACT_ANALYSIS",
  "entities": ["order.amount"],
  "constraints": {
    "depth": 3
  }
}


⸻

实现建议
	•	规则优先（稳定）
	•	LLM兜底（低频）

⸻

4️⃣ Graph Retrieval Agent（核心引擎）

⸻

职责
	•	Query-aware Graph Retrieval

⸻

输入

{
  "entities": ["order.amount"],
  "intent": "IMPACT_ANALYSIS"
}


⸻

输出

{
  "subgraph": {
    "nodes": [...],
    "edges": [...]
  }
}


⸻

内部流程

seed resolve
→ graph traversal
→ embedding recall
→ ranking
→ subgraph压缩


⸻

依赖
	•	Neo4j
	•	Vector DB

⸻

5️⃣ Impact Analysis Agent（影响传播）

⸻

职责
	•	执行 BFS + 权重传播

⸻

输入

{
  "subgraph": {...},
  "target": "order.amount"
}


⸻

输出

{
  "impacts": [
    {"node": "invoice.total", "depth": 1, "confidence": 0.8}
  ]
}


⸻

核心逻辑

confidence *= edge_weight
prune if < threshold


⸻

6️⃣ Risk Scoring Agent（风险评分）

⸻

职责
	•	输出可量化风险

⸻

输入

{
  "impact_graph": {...}
}


⸻

输出

{
  "score": 78,
  "level": "HIGH"
}


⸻

内部逻辑

blast_radius
+ critical_path
+ coupling
+ test_coverage


⸻

7️⃣ LLM Reasoning Agent（解释层）

⸻

职责
	•	解释复杂逻辑
	•	生成自然语言说明

⸻

输入

{
  "graph": {...},
  "question": "这个存储过程做什么？"
}


⸻

输出

“该过程用于生成订单发票，并更新总金额”


⸻

使用策略

仅在以下情况触发：
- 用户请求解释
- 图无法表达业务语义


⸻

8️⃣ Budget Controller Agent（成本控制）

⸻

职责
	•	控制Token使用

⸻

输入

{
  "graph_size": 30,
  "llm_required": true
}


⸻

输出

{
  "allowed": true,
  "strategy": "REDUCE_DEPTH"
}


⸻

核心规则

if token_estimate > budget:
  降级


⸻

四、Agent协作流程（关键）

⸻

场景：影响分析

User Query
  ↓
Query Parser Agent
  ↓
Graph Retrieval Agent
  ↓
Impact Analysis Agent
  ↓
Risk Scoring Agent
  ↓
LLM Agent（可选）
  ↓
Response


⸻

Orchestrator伪代码

query = parse_agent.run(user_input)

graph = retrieval_agent.run(query)

impact = impact_agent.run(graph)

risk = risk_agent.run(impact)

if need_llm:
    explanation = llm_agent.run(graph)

return assemble_response()


⸻

五、通信协议（必须标准化）

⸻

Agent接口统一格式

{
  "input": {...},
  "output": {...},
  "metadata": {
    "latency": 120,
    "confidence": 0.9
  }
}


⸻

六、失败与降级策略（生产必备）

⸻

1️⃣ Retrieval失败

→ fallback keyword search


⸻

2️⃣ 图过大

→ 限制 depth
→ 限制 node数


⸻

3️⃣ LLM失败

→ 返回结构化图结果


⸻

4️⃣ 超预算

→ 禁用LLM
→ 返回impact graph


⸻

七、并行开发建议（关键）

⸻

Team拆分

⸻

Team A（Graph组）
	•	Graph Builder Agent
	•	Lineage Agent

⸻

Team B（Retrieval组）
	•	Query Parser
	•	Graph Retrieval

⸻

Team C（Analysis组）
	•	Impact Agent
	•	Risk Agent

⸻

Team D（AI组）
	•	LLM Agent
	•	Prompt优化

⸻

Team E（Infra组）
	•	Orchestrator
	•	Budget Controller
	•	API

⸻

