from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    FUNCTION = "FUNCTION"
    PROCEDURE = "PROCEDURE"
    TABLE = "TABLE"
    COLUMN = "COLUMN"
    VIEW = "VIEW"
    MODULE = "MODULE"
    CLASS = "CLASS"
    VARIABLE = "VARIABLE"
    PARAMETER = "PARAMETER"


class EdgeType(str, Enum):
    CALL = "CALL"
    READ = "READ"
    WRITE = "WRITE"
    LINEAGE = "LINEAGE"
    CONTAINS = "CONTAINS"
    IMPORTS = "IMPORTS"
    REFERENCES = "REFERENCES"
    DERIVES_FROM = "DERIVES_FROM"


class QueryIntent(str, Enum):
    IMPACT_ANALYSIS = "IMPACT_ANALYSIS"
    LINEAGE_QUERY = "LINEAGE_QUERY"
    ARCHITECTURE_QA = "ARCHITECTURE_QA"
    REFACTOR_SUGGESTION = "REFACTOR_SUGGESTION"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    DEPENDENCY_QUERY = "DEPENDENCY_QUERY"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Node(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: NodeType
    name: str
    qualified_name: str = ""
    file_path: str = ""
    line_number: int = 0
    end_line_number: int = 0
    source_code: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return False
        return self.id == other.id


class Edge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_id: str
    target_id: str
    type: EdgeType
    weight: float = 1.0
    label: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Graph(BaseModel):
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    def add_node(self, node: Node) -> None:
        existing = {n.id for n in self.nodes}
        if node.id not in existing:
            self.nodes.append(node)

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[Node]:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def get_node_by_name(self, name: str) -> Optional[Node]:
        for n in self.nodes:
            if n.name == name or n.qualified_name == name:
                return n
        return None

    def get_outgoing_edges(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source_id == node_id]

    def get_incoming_edges(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.target_id == node_id]

    def get_neighbors(self, node_id: str, direction: str = "both") -> list[str]:
        neighbor_ids: set[str] = set()
        if direction in ("out", "both"):
            for e in self.get_outgoing_edges(node_id):
                neighbor_ids.add(e.target_id)
        if direction in ("in", "both"):
            for e in self.get_incoming_edges(node_id):
                neighbor_ids.add(e.source_id)
        return list(neighbor_ids)

    def subgraph(self, node_ids: set[str]) -> Graph:
        nodes = [n for n in self.nodes if n.id in node_ids]
        edges = [e for e in self.edges if e.source_id in node_ids and e.target_id in node_ids]
        return Graph(nodes=nodes, edges=edges)

    def node_count(self) -> int:
        return len(self.nodes)

    def edge_count(self) -> int:
        return len(self.edges)

    def estimate_tokens(self) -> int:
        return self.node_count() * 25 + self.edge_count() * 10


class LineageEdge(BaseModel):
    source: str
    target: str
    transformation: str = ""
    via: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class BusinessOntology(BaseModel):
    entity: str
    mapped_fields: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    description: str = ""


class ParsedQuery(BaseModel):
    intent: QueryIntent
    entities: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    original_query: str = ""


class ImpactNode(BaseModel):
    node_id: str
    node_name: str
    node_type: NodeType
    depth: int
    confidence: float
    path: list[str] = Field(default_factory=list)


class ImpactResult(BaseModel):
    target: str
    impacts: list[ImpactNode] = Field(default_factory=list)
    total_affected: int = 0
    max_depth: int = 0
    avg_confidence: float = 0.0


class RiskScore(BaseModel):
    score: float = Field(ge=0, le=100)
    level: RiskLevel
    factors: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""


class AgentInput(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    confidence: float = 1.0
    success: bool = True
    error: str = ""


class TokenBudget(BaseModel):
    total_budget: int = 8000
    used: int = 0
    graph_tokens: int = 0
    llm_tokens: int = 0
    strategy: str = "NORMAL"

    @property
    def remaining(self) -> int:
        return max(0, self.total_budget - self.used)

    @property
    def exceeded(self) -> bool:
        return self.used > self.total_budget

    def allocate(self, graph_tokens: int, llm_tokens: int = 0) -> bool:
        total_needed = graph_tokens + llm_tokens
        if self.used + total_needed > self.total_budget:
            return False
        self.graph_tokens = graph_tokens
        self.llm_tokens = llm_tokens
        self.used += total_needed
        return True

    def degrade(self) -> str:
        if self.llm_tokens > 0:
            self.used -= self.llm_tokens
            self.llm_tokens = 0
            self.strategy = "NO_LLM"
            return "NO_LLM"
        if self.graph_tokens > 0:
            reduction = self.graph_tokens // 2
            self.used -= reduction
            self.graph_tokens -= reduction
            self.strategy = "REDUCE_DEPTH"
            return "REDUCE_DEPTH"
        self.strategy = "MINIMAL"
        return "MINIMAL"


class CodeFile(BaseModel):
    path: str
    language: str
    content: str
    size: int = 0


class RepositoryConfig(BaseModel):
    repo_path: str
    language: str = "sql"
    exclude_patterns: list[str] = Field(default_factory=lambda: ["*.test.*", "__pycache__", "node_modules", ".git"])
    include_patterns: list[str] = Field(default_factory=lambda: ["*.sql", "*.java", "*.py"])
