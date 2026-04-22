from __future__ import annotations

from typing import Any, Optional

from codemind.core.config import get_config
from codemind.core.models import Edge, EdgeType, Graph, Node, NodeType


class Neo4jStore:
    def __init__(self) -> None:
        self._config = get_config()
        self._driver: Any = None
        self._connected = False

    def connect(self) -> bool:
        try:
            from neo4j import GraphDatabase
            self._driver = GraphDatabase.driver(
                self._config.neo4j_uri,
                auth=(self._config.neo4j_user, self._config.neo4j_password),
            )
            self._driver.verify_connectivity()
            self._connected = True
            return True
        except Exception:
            self._connected = False
            return False

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def store_graph(self, graph: Graph) -> int:
        if not self._connected:
            return 0

        count = 0
        with self._driver.session(database=self._config.neo4j_database) as session:
            for node in graph.nodes:
                session.execute_write(self._create_node_tx, node)
                count += 1

            for edge in graph.edges:
                session.execute_write(self._create_edge_tx, edge)
                count += 1

        return count

    def store_nodes(self, nodes: list[Node]) -> int:
        if not self._connected:
            return 0

        count = 0
        with self._driver.session(database=self._config.neo4j_database) as session:
            for node in nodes:
                session.execute_write(self._create_node_tx, node)
                count += 1

        return count

    def store_edges(self, edges: list[Edge]) -> int:
        if not self._connected:
            return 0

        count = 0
        with self._driver.session(database=self._config.neo4j_database) as session:
            for edge in edges:
                session.execute_write(self._create_edge_tx, edge)
                count += 1

        return count

    def query_nodes(self, node_type: Optional[NodeType] = None,
                     name_pattern: str = "") -> list[Node]:
        if not self._connected:
            return []

        with self._driver.session(database=self._config.neo4j_database) as session:
            result = session.execute_read(self._query_nodes_tx, node_type, name_pattern)
            return result

    def query_neighbors(self, node_id: str, max_depth: int = 3) -> Graph:
        if not self._connected:
            return Graph()

        with self._driver.session(database=self._config.neo4j_database) as session:
            return session.execute_read(self._query_neighbors_tx, node_id, max_depth)

    def query_lineage(self, node_name: str, direction: str = "both",
                       max_depth: int = 5) -> Graph:
        if not self._connected:
            return Graph()

        with self._driver.session(database=self._config.neo4j_database) as session:
            return session.execute_read(self._query_lineage_tx, node_name, direction, max_depth)

    def clear_all(self) -> None:
        if not self._connected:
            return

        with self._driver.session(database=self._config.neo4j_database) as session:
            session.run("MATCH (n) DETACH DELETE n")

    @staticmethod
    def _create_node_tx(tx: Any, node: Node) -> None:
        props = {
            "id": node.id,
            "name": node.name,
            "qualified_name": node.qualified_name,
            "file_path": node.file_path,
            "line_number": node.line_number,
            "source_code": node.source_code[:2000] if node.source_code else "",
        }
        props.update(node.metadata)

        query = f"""
        MERGE (n:{node.type.value} {{id: $id}})
        SET n += $props
        """
        tx.run(query, id=node.id, props=props)

    @staticmethod
    def _create_edge_tx(tx: Any, edge: Edge) -> None:
        props = {
            "weight": edge.weight,
            "label": edge.label,
        }
        props.update(edge.metadata)

        query = f"""
        MATCH (a {{id: $source_id}})
        MATCH (b {{id: $target_id}})
        MERGE (a)-[r:{edge.type.value}]->(b)
        SET r += $props
        """
        tx.run(query, source_id=edge.source_id, target_id=edge.target_id, props=props)

    @staticmethod
    def _query_nodes_tx(tx: Any, node_type: Optional[NodeType],
                          name_pattern: str) -> list[Node]:
        if node_type and name_pattern:
            query = f"""
            MATCH (n:{node_type.value})
            WHERE n.name CONTAINS $pattern OR n.qualified_name CONTAINS $pattern
            RETURN n
            LIMIT 100
            """
            result = tx.run(query, pattern=name_pattern)
        elif node_type:
            query = f"MATCH (n:{node_type.value}) RETURN n LIMIT 100"
            result = tx.run(query)
        elif name_pattern:
            query = """
            MATCH (n)
            WHERE n.name CONTAINS $pattern OR n.qualified_name CONTAINS $pattern
            RETURN n LIMIT 100
            """
            result = tx.run(query, pattern=name_pattern)
        else:
            query = "MATCH (n) RETURN n LIMIT 100"
            result = tx.run(query)

        nodes = []
        for record in result:
            n = dict(record["n"])
            node_type_str = list(record["n"].labels)[0] if record["n"].labels else "FUNCTION"
            nodes.append(Node(
                id=n.get("id", ""),
                type=NodeType(node_type_str),
                name=n.get("name", ""),
                qualified_name=n.get("qualified_name", ""),
                file_path=n.get("file_path", ""),
                line_number=n.get("line_number", 0),
                source_code=n.get("source_code", ""),
            ))
        return nodes

    @staticmethod
    def _query_neighbors_tx(tx: Any, node_id: str, max_depth: int) -> Graph:
        query = """
        CALL apoc.path.expandConfig($start, {
            relationshipFilter: "CALL|READ|WRITE|LINEAGE|CONTAINS|REFERENCES",
            maxLevel: $depth
        })
        YIELD path
        RETURN path
        """
        try:
            result = tx.run(query, start=node_id, depth=max_depth)
        except Exception:
            query = """
            MATCH (start {id: $start})-[r*1..3]-(other)
            RETURN start, r, other
            LIMIT 100
            """
            result = tx.run(query, start=node_id)

        nodes: dict[str, Node] = {}
        edges: list[Edge] = []

        for record in result:
            if "path" in record:
                path = record["path"]
                for node in path.nodes:
                    n = dict(node)
                    labels = list(node.labels)
                    nt = labels[0] if labels else "FUNCTION"
                    try:
                        node_type = NodeType(nt)
                    except ValueError:
                        node_type = NodeType.FUNCTION
                    nid = n.get("id", "")
                    if nid and nid not in nodes:
                        nodes[nid] = Node(
                            id=nid,
                            type=node_type,
                            name=n.get("name", ""),
                            qualified_name=n.get("qualified_name", ""),
                        )
                for rel in path.relationships:
                    try:
                        edge_type = EdgeType(type(rel).__name__)
                    except ValueError:
                        edge_type = EdgeType.REFERENCES
                    edges.append(Edge(
                        source_id=rel.start_node.get("id", ""),
                        target_id=rel.end_node.get("id", ""),
                        type=edge_type,
                        weight=rel.get("weight", 1.0),
                    ))
            else:
                for key in ["start", "other"]:
                    if key in record:
                        node = record[key]
                        n = dict(node)
                        labels = list(node.labels)
                        nt = labels[0] if labels else "FUNCTION"
                        try:
                            node_type = NodeType(nt)
                        except ValueError:
                            node_type = NodeType.FUNCTION
                        nid = n.get("id", "")
                        if nid and nid not in nodes:
                            nodes[nid] = Node(
                                id=nid,
                                type=node_type,
                                name=n.get("name", ""),
                                qualified_name=n.get("qualified_name", ""),
                            )

        return Graph(nodes=list(nodes.values()), edges=edges)

    @staticmethod
    def _query_lineage_tx(tx: Any, node_name: str, direction: str,
                            max_depth: int) -> Graph:
        if direction == "forward":
            rel_pattern = "LINEAGE|WRITE|READ"
        elif direction == "backward":
            rel_pattern = "<LINEAGE|<WRITE|<READ"
        else:
            rel_pattern = "LINEAGE|WRITE|READ|<LINEAGE|<WRITE|<READ"

        query = """
        CALL apoc.path.expandConfig($start, {
            relationshipFilter: $rel_filter,
            maxLevel: $depth
        })
        YIELD path
        RETURN path
        """
        try:
            result = tx.run(query, start=node_name, rel_filter=rel_pattern, depth=max_depth)
        except Exception:
            query = """
            MATCH (start {name: $start})-[r*1..5]-(other)
            RETURN start, r, other
            LIMIT 100
            """
            result = tx.run(query, start=node_name)

        nodes: dict[str, Node] = {}
        edges: list[Edge] = []

        for record in result:
            if "path" in record:
                path = record["path"]
                for node in path.nodes:
                    n = dict(node)
                    labels = list(node.labels)
                    nt = labels[0] if labels else "TABLE"
                    try:
                        node_type = NodeType(nt)
                    except ValueError:
                        node_type = NodeType.TABLE
                    nid = n.get("id", "")
                    if nid and nid not in nodes:
                        nodes[nid] = Node(
                            id=nid,
                            type=node_type,
                            name=n.get("name", ""),
                            qualified_name=n.get("qualified_name", ""),
                        )
                for rel in path.relationships:
                    try:
                        edge_type = EdgeType(type(rel).__name__)
                    except ValueError:
                        edge_type = EdgeType.LINEAGE
                    edges.append(Edge(
                        source_id=rel.start_node.get("id", ""),
                        target_id=rel.end_node.get("id", ""),
                        type=edge_type,
                        weight=rel.get("weight", 1.0),
                    ))

        return Graph(nodes=list(nodes.values()), edges=edges)
