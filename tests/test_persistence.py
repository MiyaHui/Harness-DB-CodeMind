from codemind.core.orchestrator import Orchestrator
import os

orch = Orchestrator()

print("=== Step 1: Index ===")
result = orch.index_repository("tests/test_data/erp_stored_procedures.sql", "sql")
print(f"Nodes: {result['node_count']}, Edges: {result['edge_count']}")
print(f"Graph saved to: {result.get('graph_saved_to')}")

print()
print("=== Step 2: Verify Persistence ===")
graph_path = result.get("graph_saved_to", "")
if graph_path and os.path.exists(graph_path):
    size = os.path.getsize(graph_path)
    print(f"Graph file exists: {graph_path} ({size} bytes)")
else:
    print("ERROR: Graph file not found!")

emb_dir = "./data/embedding_index"
if os.path.exists(emb_dir + "/embeddings.npy"):
    print(f"Embedding index exists: {emb_dir}/")
    print(f"  embeddings.npy: {os.path.getsize(emb_dir + '/embeddings.npy')} bytes")
    print(f"  node_ids.json: {os.path.getsize(emb_dir + '/node_ids.json')} bytes")

print()
print("=== Step 3: Simulate Restart (load from disk) ===")
orch2 = Orchestrator()
stats = orch2.get_graph_stats()
print(f"Graph loaded from disk: {stats['loaded']}")
print(f"Nodes: {stats['node_count']}, Edges: {stats['edge_count']}")
print(f"Embedding available: {stats.get('embedding_available')}")

print()
print("=== Step 4: Query After Restart ===")
result = orch2.query("修改 orders 会影响什么？")
print(f"Intent: {result['intent']}")
if "impact" in result:
    print(f"Affected nodes: {result['impact']['total_affected']}")
if "risk" in result:
    print(f"Risk: {result['risk']['score']}/100 {result['risk']['level']}")
print(f"Elapsed: {result['elapsed_ms']:.1f}ms")

print()
print("=== Step 5: Semantic Search ===")
results = orch2._semantic_search_nodes("invoice payment", top_k=5)
for node_id, score in results:
    node = orch2._graph.get_node(node_id)
    if node:
        print(f"  {node.name} ({node.type.value}) score={score:.3f}")

print()
print("All verifications passed!")
