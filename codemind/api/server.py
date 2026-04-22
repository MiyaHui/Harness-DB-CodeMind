from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from codemind.core.orchestrator import Orchestrator


app = FastAPI(
    title="Harness-DB-CodeMind",
    description="Enterprise AI Code Intelligence Infrastructure - Codebase Digital Twin System",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


class IndexRequest(BaseModel):
    repo_path: str = Field(..., description="Path to the repository to index")
    language: str = Field(default="sql", description="Primary language (sql/java/python)")


class QueryRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    budget: int = Field(default=0, description="Token budget (0 = use default)")


class QueryResponse(BaseModel):
    success: bool
    query: str = ""
    intent: str = ""
    entities: list[str] = Field(default_factory=list)
    impact: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    lineage: dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
    elapsed_ms: float = 0.0
    error: str = ""


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "harness-db-codemind"}


@app.post("/index")
async def index_repository(request: IndexRequest):
    orch = get_orchestrator()
    result = orch.index_repository(request.repo_path, request.language)
    if not result["success"]:
        raise HTTPException(status_code=500, detail=result.get("error", "Indexing failed"))
    return result


@app.post("/query", response_model=QueryResponse)
async def query_codebase(request: QueryRequest):
    orch = get_orchestrator()
    result = orch.query(request.query, request.budget)
    return QueryResponse(**{k: v for k, v in result.items() if k in QueryResponse.model_fields})


@app.get("/stats")
async def get_stats():
    orch = get_orchestrator()
    return orch.get_graph_stats()


@app.get("/graph/nodes")
async def get_nodes(node_type: Optional[str] = None, pattern: str = ""):
    orch = get_orchestrator()
    if not orch._graph:
        raise HTTPException(status_code=404, detail="No graph loaded")
    from codemind.core.models import NodeType
    nt = NodeType(node_type) if node_type else None
    nodes = []
    for n in orch._graph.nodes:
        if nt and n.type != nt:
            continue
        if pattern and pattern.lower() not in n.name.lower():
            continue
        nodes.append(n.model_dump())
    return {"nodes": nodes, "count": len(nodes)}


@app.get("/graph/edges")
async def get_edges(edge_type: Optional[str] = None):
    orch = get_orchestrator()
    if not orch._graph:
        raise HTTPException(status_code=404, detail="No graph loaded")
    from codemind.core.models import EdgeType
    et = EdgeType(edge_type) if edge_type else None
    edges = []
    for e in orch._graph.edges:
        if et and e.type != et:
            continue
        edges.append(e.model_dump())
    return {"edges": edges, "count": len(edges)}
