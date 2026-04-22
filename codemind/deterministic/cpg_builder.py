from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional

from codemind.core.models import Edge, EdgeType, Graph, Node, NodeType


class CPGBuilder:
    def __init__(self) -> None:
        self._node_registry: dict[str, Node] = {}
        self._edges: list[Edge] = []

    def build_from_sql_file(self, file_path: str) -> Graph:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return self.build_from_sql(content, file_path=file_path)

    def build_from_sql(self, sql: str, file_path: str = "") -> Graph:
        self._node_registry = {}
        self._edges = []

        procedures = self._extract_procedures(sql, file_path)
        for proc in procedures:
            self._node_registry[proc.id] = proc

        for proc in procedures:
            self._analyze_procedure_body(proc, sql)

        tables = self._extract_table_references(sql, file_path)
        for table in tables:
            if table.id not in self._node_registry:
                self._node_registry[table.id] = table

        columns = self._extract_column_references(sql, file_path)
        for col in columns:
            if col.id not in self._node_registry:
                self._node_registry[col.id] = col
            parent_table = col.metadata.get("parent_table", "")
            if parent_table:
                table_id = f"table_{parent_table.lower()}"
                if table_id in self._node_registry:
                    self._add_edge(col.id, table_id, EdgeType.CONTAINS)

        return Graph(
            nodes=list(self._node_registry.values()),
            edges=self._edges,
        )

    def build_from_java_file(self, file_path: str) -> Graph:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return self.build_from_java(content, file_path=file_path)

    def build_from_java(self, java_code: str, file_path: str = "") -> Graph:
        self._node_registry = {}
        self._edges = []

        classes = self._extract_java_classes(java_code, file_path)
        for cls in classes:
            self._node_registry[cls.id] = cls

        methods = self._extract_java_methods(java_code, file_path)
        for method in methods:
            if method.id not in self._node_registry:
                self._node_registry[method.id] = method
            parent_class = method.metadata.get("parent_class", "")
            if parent_class:
                class_id = f"class_{parent_class.lower()}"
                if class_id in self._node_registry:
                    self._add_edge(class_id, method.id, EdgeType.CONTAINS)

        for method in methods:
            self._analyze_java_method_calls(method, java_code)

        return Graph(
            nodes=list(self._node_registry.values()),
            edges=self._edges,
        )

    def build_from_python_file(self, file_path: str) -> Graph:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        return self.build_from_python(content, file_path=file_path)

    def build_from_python(self, python_code: str, file_path: str = "") -> Graph:
        self._node_registry = {}
        self._edges = []

        classes = self._extract_python_classes(python_code, file_path)
        for cls in classes:
            self._node_registry[cls.id] = cls

        functions = self._extract_python_functions(python_code, file_path)
        for func in functions:
            if func.id not in self._node_registry:
                self._node_registry[func.id] = func
            parent_class = func.metadata.get("parent_class", "")
            if parent_class:
                class_id = f"class_{parent_class.lower()}"
                if class_id in self._node_registry:
                    self._add_edge(class_id, func.id, EdgeType.CONTAINS)

        for func in functions:
            self._analyze_python_function_calls(func, python_code)

        return Graph(
            nodes=list(self._node_registry.values()),
            edges=self._edges,
        )

    def build_from_directory(self, dir_path: str) -> Graph:
        combined_graph = Graph()
        path = Path(dir_path)

        if not path.exists():
            return combined_graph

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules", ".idea", "venv", ".venv"}]
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    if file.endswith(".sql"):
                        sub = self.build_from_sql_file(file_path)
                    elif file.endswith(".java"):
                        sub = self.build_from_java_file(file_path)
                    elif file.endswith(".py"):
                        sub = self.build_from_python_file(file_path)
                    else:
                        continue
                    self._merge_graphs(combined_graph, sub)
                except Exception:
                    continue

        return combined_graph

    def _merge_graphs(self, target: Graph, source: Graph) -> None:
        for node in source.nodes:
            if node.id not in {n.id for n in target.nodes}:
                target.nodes.append(node)
        for edge in source.edges:
            target.edges.append(edge)

    def _extract_procedures(self, sql: str, file_path: str = "") -> list[Node]:
        nodes: list[Node] = []
        patterns = [
            (r"(?:CREATE|ALTER)\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+(\w+)", NodeType.PROCEDURE),
            (r"(?:CREATE|ALTER)\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(\w+)", NodeType.FUNCTION),
        ]

        for pattern, node_type in patterns:
            for match in re.finditer(pattern, sql, re.IGNORECASE):
                name = match.group(1)
                node_id = f"proc_{name.lower()}"
                if node_id not in self._node_registry:
                    body = self._extract_procedure_body(sql, match.start())
                    nodes.append(Node(
                        id=node_id,
                        type=node_type,
                        name=name,
                        qualified_name=name,
                        file_path=file_path,
                        source_code=body,
                        metadata={"start_pos": match.start()},
                    ))
        return nodes

    def _extract_procedure_body(self, sql: str, start_pos: int = 0) -> str:
        remaining = sql[start_pos:]
        match = re.search(r"(?:AS|IS|BEGIN)\s*(.*?)\s*END\b", remaining, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _analyze_procedure_body(self, proc: Node, full_sql: str) -> None:
        body = proc.source_code
        if not body:
            return

        exec_pattern = r"(?:EXEC|EXECUTE|CALL)\s+(\w+)"
        for match in re.finditer(exec_pattern, body, re.IGNORECASE):
            called_proc = match.group(1)
            called_id = f"proc_{called_proc.lower()}"
            self._add_edge(proc.id, called_id, EdgeType.CALL)

        insert_pattern = r"INSERT\s+INTO\s+(\w+)"
        for match in re.finditer(insert_pattern, body, re.IGNORECASE):
            table_name = match.group(1)
            table_id = f"table_{table_name.lower()}"
            self._add_edge(proc.id, table_id, EdgeType.WRITE)

        update_pattern = r"UPDATE\s+(\w+)\s+SET"
        for match in re.finditer(update_pattern, body, re.IGNORECASE):
            table_name = match.group(1)
            table_id = f"table_{table_name.lower()}"
            self._add_edge(proc.id, table_id, EdgeType.WRITE)

        delete_pattern = r"DELETE\s+FROM\s+(\w+)"
        for match in re.finditer(delete_pattern, body, re.IGNORECASE):
            table_name = match.group(1)
            table_id = f"table_{table_name.lower()}"
            self._add_edge(proc.id, table_id, EdgeType.WRITE)

        select_pattern = r"(?:FROM|JOIN)\s+(\w+)"
        for match in re.finditer(select_pattern, body, re.IGNORECASE):
            table_name = match.group(1)
            if table_name.upper() not in ("SELECT", "WHERE", "SET", "AND", "OR", "ON", "AS", "INTO"):
                table_id = f"table_{table_name.lower()}"
                self._add_edge(proc.id, table_id, EdgeType.READ)

    def _extract_table_references(self, sql: str, file_path: str = "") -> list[Node]:
        nodes: list[Node] = []
        seen: set[str] = set()

        patterns = [
            r"(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+(\w+)",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, sql, re.IGNORECASE):
                name = match.group(1)
                if name.upper() in ("SELECT", "WHERE", "SET", "AND", "OR", "ON", "AS", "DUAL", "VALUES"):
                    continue
                node_id = f"table_{name.lower()}"
                if node_id not in seen and node_id not in self._node_registry:
                    seen.add(node_id)
                    nodes.append(Node(
                        id=node_id,
                        type=NodeType.TABLE,
                        name=name,
                        qualified_name=name,
                        file_path=file_path,
                    ))
        return nodes

    def _extract_column_references(self, sql: str, file_path: str = "") -> list[Node]:
        nodes: list[Node] = []
        seen: set[str] = set()

        pattern = r'(\w+)\.(\w+)'
        for match in re.finditer(pattern, sql):
            table_name = match.group(1)
            col_name = match.group(2)
            if table_name.upper() in ("SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"):
                continue
            if col_name.upper() in ("*",):
                continue
            col_id = f"col_{table_name.lower()}_{col_name.lower()}"
            if col_id not in seen and col_id not in self._node_registry:
                seen.add(col_id)
                nodes.append(Node(
                    id=col_id,
                    type=NodeType.COLUMN,
                    name=col_name,
                    qualified_name=f"{table_name}.{col_name}",
                    file_path=file_path,
                    metadata={"parent_table": table_name},
                ))
        return nodes

    def _extract_java_classes(self, java_code: str, file_path: str = "") -> list[Node]:
        nodes: list[Node] = []
        pattern = r'(?:public|private|protected)?\s*(?:abstract\s+)?(?:class|interface)\s+(\w+)'
        for match in re.finditer(pattern, java_code):
            name = match.group(1)
            nodes.append(Node(
                id=f"class_{name.lower()}",
                type=NodeType.CLASS,
                name=name,
                qualified_name=name,
                file_path=file_path,
            ))
        return nodes

    def _extract_java_methods(self, java_code: str, file_path: str = "") -> list[Node]:
        nodes: list[Node] = []
        pattern = r'(?:public|private|protected)?\s*(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+[\w,\s]+)?\s*\{'
        current_class = ""
        class_pattern = r'(?:public|private|protected)?\s*(?:abstract\s+)?class\s+(\w+)'

        class_matches = list(re.finditer(class_pattern, java_code))
        for match in re.finditer(pattern, java_code):
            method_name = match.group(1)
            if method_name in ("if", "while", "for", "switch", "catch", "return", "new"):
                continue
            for cls_match in class_matches:
                if cls_match.start() < match.start():
                    current_class = cls_match.group(1)
            nodes.append(Node(
                id=f"func_{current_class.lower()}_{method_name.lower()}" if current_class else f"func_{method_name.lower()}",
                type=NodeType.FUNCTION,
                name=method_name,
                qualified_name=f"{current_class}.{method_name}" if current_class else method_name,
                file_path=file_path,
                metadata={"parent_class": current_class} if current_class else {},
            ))
        return nodes

    def _analyze_java_method_calls(self, method: Node, java_code: str) -> None:
        pattern = r'(\w+)\.(\w+)\s*\('
        for match in re.finditer(pattern, java_code):
            obj = match.group(1)
            called_method = match.group(2)
            if called_method in ("toString", "equals", "hashCode", "getClass"):
                continue
            called_id = f"func_{obj.lower()}_{called_method.lower()}"
            self._add_edge(method.id, called_id, EdgeType.CALL)

    def _extract_python_classes(self, python_code: str, file_path: str = "") -> list[Node]:
        nodes: list[Node] = []
        pattern = r'class\s+(\w+)(?:\([^)]*\))?:'
        for match in re.finditer(pattern, python_code):
            name = match.group(1)
            nodes.append(Node(
                id=f"class_{name.lower()}",
                type=NodeType.CLASS,
                name=name,
                qualified_name=name,
                file_path=file_path,
            ))
        return nodes

    def _extract_python_functions(self, python_code: str, file_path: str = "") -> list[Node]:
        nodes: list[Node] = []
        pattern = r'(?:async\s+)?def\s+(\w+)\s*\('
        current_class = ""
        class_pattern = r'class\s+(\w+)'
        class_matches = list(re.finditer(class_pattern, python_code))

        for match in re.finditer(pattern, python_code):
            func_name = match.group(1)
            for cls_match in class_matches:
                if cls_match.start() < match.start():
                    current_class = cls_match.group(1)
            nodes.append(Node(
                id=f"func_{current_class.lower()}_{func_name.lower()}" if current_class else f"func_{func_name.lower()}",
                type=NodeType.FUNCTION,
                name=func_name,
                qualified_name=f"{current_class}.{func_name}" if current_class else func_name,
                file_path=file_path,
                metadata={"parent_class": current_class} if current_class else {},
            ))
        return nodes

    def _analyze_python_function_calls(self, func: Node, python_code: str) -> None:
        pattern = r'(\w+)\.(\w+)\s*\('
        for match in re.finditer(pattern, python_code):
            obj = match.group(1)
            called_func = match.group(2)
            if called_func.startswith("_"):
                continue
            called_id = f"func_{obj.lower()}_{called_func.lower()}"
            self._add_edge(func.id, called_id, EdgeType.CALL)

    def _add_edge(self, source_id: str, target_id: str, edge_type: EdgeType, weight: float = 1.0) -> None:
        edge = Edge(
            source_id=source_id,
            target_id=target_id,
            type=edge_type,
            weight=weight,
        )
        self._edges.append(edge)
