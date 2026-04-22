from codemind.deterministic.sql_parser import SQLParser
from codemind.deterministic.cpg_builder import CPGBuilder
from codemind.deterministic.program_slicer import ProgramSlicer
from codemind.agents.query_parser import QueryParserAgent
from codemind.agents.impact_analysis import ImpactAnalysisAgent
from codemind.agents.risk_scoring import RiskScoringAgent
from codemind.agents.lineage_builder import LineageBuilderAgent
from codemind.agents.budget_controller import BudgetControllerAgent
from codemind.core.models import AgentInput, QueryIntent
from codemind.core.orchestrator import Orchestrator


def test_sql_parser():
    parser = SQLParser()
    sql = """
    INSERT INTO invoice (order_id, total_amount)
    SELECT o.id, o.total_amount * 1.08
    FROM orders o
    WHERE o.status = 'PAID';
    """
    statements = parser.parse(sql)
    assert len(statements) >= 1
    stmt = statements[0]
    assert stmt.stmt_type == "INSERT"
    assert len(stmt.column_lineage) > 0
    print(f"  SQL Parser: {len(statements)} statements, {len(stmt.column_lineage)} lineage edges")


def test_cpg_builder():
    builder = CPGBuilder()
    sql = """
    CREATE PROCEDURE sp_test
    AS
    BEGIN
        INSERT INTO target_table (col1) SELECT a.col1 FROM source_table a;
        EXEC sp_other_proc;
    END
    """
    graph = builder.build_from_sql(sql)
    assert graph.node_count() > 0
    assert graph.edge_count() > 0
    print(f"  CPG Builder: {graph.node_count()} nodes, {graph.edge_count()} edges")


def test_program_slicer():
    builder = CPGBuilder()
    sql = """
    CREATE PROCEDURE sp_main AS BEGIN EXEC sp_sub1; EXEC sp_sub2; END
    CREATE PROCEDURE sp_sub1 AS BEGIN INSERT INTO t1 SELECT * FROM t2; END
    CREATE PROCEDURE sp_sub2 AS BEGIN UPDATE t3 SET col1 = 1; END
    """
    graph = builder.build_from_sql(sql)
    slicer = ProgramSlicer(graph)
    proc_node = None
    for n in graph.nodes:
        if n.name == "sp_main":
            proc_node = n
            break
    if proc_node:
        forward = slicer.slice_forward(proc_node.id)
        assert forward.node_count() > 0
        print(f"  Program Slicer: forward slice has {forward.node_count()} nodes")
    else:
        print("  Program Slicer: skipped (no sp_main found)")


def test_query_parser():
    parser = QueryParserAgent()
    result = parser.run(AgentInput(data={"query": "修改 order.amount 会影响什么？"}))
    assert result.success
    assert result.data["intent"] == "IMPACT_ANALYSIS"
    assert len(result.data["entities"]) > 0
    print(f"  Query Parser: intent={result.data['intent']}, entities={result.data['entities']}")


def test_lineage_builder():
    builder = LineageBuilderAgent()
    sql = """
    INSERT INTO invoice (order_id, total_amount, tax)
    SELECT o.id, o.total_amount, o.total_amount * 0.08
    FROM orders o;
    """
    result = builder.run(AgentInput(data={"sql": sql}))
    assert result.success
    assert result.data["lineage_count"] > 0
    print(f"  Lineage Builder: {result.data['lineage_count']} lineage edges")


def test_budget_controller():
    controller = BudgetControllerAgent()
    result = controller.run(AgentInput(data={
        "graph_size": 100,
        "edge_size": 200,
        "llm_required": True,
        "budget": 8000,
    }))
    assert result.success
    print(f"  Budget Controller: strategy={result.data['strategy']}, used={result.data['total_used']}")


def test_orchestrator_with_test_data():
    import os
    test_file = os.path.join(os.path.dirname(__file__), "test_data", "ecommerce_procedures.sql")
    if not os.path.exists(test_file):
        print("  Orchestrator: skipped (test data not found)")
        return

    orch = Orchestrator()
    result = orch.index_repository(test_file, "sql")
    assert result["success"]
    assert result["node_count"] > 0
    print(f"  Orchestrator Index: {result['node_count']} nodes, {result['edge_count']} edges")

    query_result = orch.query("修改 orders.total_amount 会影响什么？")
    assert query_result["success"]
    print(f"  Orchestrator Query: intent={query_result.get('intent')}, elapsed={query_result.get('elapsed_ms', 0):.1f}ms")

    if "impact" in query_result:
        print(f"    Impact: {query_result['impact'].get('total_affected', 0)} affected nodes")
    if "risk" in query_result:
        print(f"    Risk: score={query_result['risk'].get('score', 0)}, level={query_result['risk'].get('level', 'UNKNOWN')}")


if __name__ == "__main__":
    print("Running Harness-DB-CodeMind Tests...\n")

    test_sql_parser()
    test_cpg_builder()
    test_program_slicer()
    test_query_parser()
    test_lineage_builder()
    test_budget_controller()
    test_orchestrator_with_test_data()

    print("\n✓ All tests passed!")
