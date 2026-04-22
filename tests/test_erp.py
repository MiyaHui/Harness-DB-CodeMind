from codemind.core.orchestrator import Orchestrator
import json

orch = Orchestrator()

print("=" * 60)
print("Test 1: Index ERP Stored Procedures")
print("=" * 60)
result = orch.index_repository("tests/test_data/erp_stored_procedures.sql", "sql")
print(f"Index result: nodes={result.get('node_count')}, edges={result.get('edge_count')}, tokens={result.get('token_estimate')}")

print()
print("=" * 60)
print("Test 2: Impact Analysis - What does changing orders affect?")
print("=" * 60)
result = orch.query("修改 orders 会影响什么？")
print(f"Intent: {result.get('intent')}")
print(f"Entities: {result.get('entities')}")
if "impact" in result:
    impact = result["impact"]
    print(f"Affected nodes: {impact.get('total_affected')}")
    print(f"Max depth: {impact.get('max_depth')}")
    print(f"Avg confidence: {impact.get('avg_confidence', 0):.3f}")
    for imp in impact.get("impacts", [])[:8]:
        path_str = " -> ".join(imp.get("path", []))
        print(f"  - {imp['node_name']} ({imp['node_type']}) depth={imp['depth']} conf={imp['confidence']:.3f} path={path_str}")
if "risk" in result:
    risk = result["risk"]
    print(f"Risk score: {risk.get('score')}/100 level={risk.get('level')}")

print()
print("=" * 60)
print("Test 3: Risk Assessment - Changing m_storage")
print("=" * 60)
result = orch.query("修改 m_storage 的风险")
print(f"Intent: {result.get('intent')}")
print(f"Entities: {result.get('entities')}")
if "impact" in result:
    impact = result["impact"]
    print(f"Affected nodes: {impact.get('total_affected')}")
    for imp in impact.get("impacts", [])[:5]:
        print(f"  - {imp['node_name']} ({imp['node_type']}) depth={imp['depth']} conf={imp['confidence']:.3f}")
if "risk" in result:
    risk = result["risk"]
    print(f"Risk score: {risk.get('score')}/100 level={risk.get('level')}")
    print(f"Risk factors: {json.dumps(risk.get('factors'), indent=2)}")
    print(f"Explanation: {risk.get('explanation')}")

print()
print("=" * 60)
print("Test 4: Lineage Query - c_invoice data sources")
print("=" * 60)
result = orch.query("c_invoice 的血缘关系")
print(f"Intent: {result.get('intent')}")
print(f"Entities: {result.get('entities')}")
if "lineage" in result:
    lineage = result["lineage"]
    print(f"Lineage edges: {lineage.get('lineage_count')}")
    for le in lineage.get("lineage_edges", [])[:8]:
        print(f"  - {le['source']} -> {le['target']} [{le['transformation']}] via={le['via']}")
if "impact" in result:
    print(f"Also found {result['impact'].get('total_affected')} affected nodes")

print()
print("=" * 60)
print("Test 5: Architecture QA - sp_complete_order")
print("=" * 60)
result = orch.query("sp_complete_order 是做什么的")
print(f"Intent: {result.get('intent')}")
print(f"Entities: {result.get('entities')}")
if "impact" in result:
    print(f"Related nodes: {result['impact'].get('total_affected')}")

print()
print("=" * 60)
print("All tests completed!")
print("=" * 60)
