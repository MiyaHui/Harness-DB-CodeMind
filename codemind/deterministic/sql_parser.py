from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import sqlparse
from sqlparse.sql import (
    Comment,
    Comparison,
    Function,
    Identifier,
    IdentifierList,
    Parenthesis,
    Where,
)
from sqlparse.tokens import DML, Keyword, Name, Punctuation, Wildcard

from codemind.core.models import EdgeType, LineageEdge, Node, NodeType


@dataclass
class TableReference:
    name: str
    alias: str = ""
    columns: list[str] = field(default_factory=list)

    @property
    def qualified_columns(self) -> list[str]:
        if self.columns:
            return [f"{self.name}.{c}" for c in self.columns]
        return []


@dataclass
class SQLStatement:
    stmt_type: str
    raw_sql: str
    source_tables: list[TableReference] = field(default_factory=list)
    target_tables: list[TableReference] = field(default_factory=list)
    column_lineage: list[LineageEdge] = field(default_factory=list)
    procedure_name: str = ""


class SQLParser:
    def __init__(self) -> None:
        self._alias_map: dict[str, str] = {}

    def parse(self, sql: str, procedure_name: str = "") -> list[SQLStatement]:
        statements = []
        parsed = sqlparse.parse(sql)
        for stmt in parsed:
            stmt_type = stmt.get_type()
            if stmt_type in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                result = self._parse_statement(stmt, procedure_name)
                if result:
                    statements.append(result)
            elif stmt_type is None:
                sql_str = str(stmt).strip().upper()
                if any(kw in sql_str for kw in ("INSERT", "UPDATE", "DELETE", "SELECT")):
                    result = self._parse_statement(stmt, procedure_name)
                    if result:
                        statements.append(result)
        return statements

    def parse_procedure(self, sql: str, proc_name: str = "") -> list[SQLStatement]:
        proc_name = proc_name or self._extract_procedure_name(sql)
        inner_sql = self._extract_procedure_body(sql)
        if not inner_sql:
            inner_sql = sql
        return self.parse(inner_sql, procedure_name=proc_name)

    def _extract_procedure_name(self, sql: str) -> str:
        patterns = [
            r"(?:CREATE|ALTER)\s+(?:OR\s+REPLACE\s+)?(?:PROCEDURE|FUNCTION)\s+(\w+)",
            r"PROCEDURE\s+(\w+)\s*\(",
        ]
        for pattern in patterns:
            match = re.search(pattern, sql, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def _extract_procedure_body(self, sql: str) -> str:
        match = re.search(r"(?:AS|IS|BEGIN)\s*(.*)\s*END", sql, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1)
        return sql

    def _parse_statement(self, stmt: sqlparse.sql.Statement, procedure_name: str = "") -> Optional[SQLStatement]:
        sql_str = str(stmt).strip().upper()
        if sql_str.startswith("INSERT"):
            return self._parse_insert(stmt, procedure_name)
        elif sql_str.startswith("UPDATE"):
            return self._parse_update(stmt, procedure_name)
        elif sql_str.startswith("DELETE"):
            return self._parse_delete(stmt, procedure_name)
        elif sql_str.startswith("SELECT"):
            return self._parse_select(stmt, procedure_name)
        return None

    def _parse_select(self, stmt: sqlparse.sql.Statement, procedure_name: str = "") -> SQLStatement:
        self._alias_map = {}
        source_tables = self._extract_from_tables(stmt)
        column_lineage = self._extract_select_lineage(stmt, source_tables)

        return SQLStatement(
            stmt_type="SELECT",
            raw_sql=str(stmt).strip(),
            source_tables=source_tables,
            target_tables=[],
            column_lineage=column_lineage,
            procedure_name=procedure_name,
        )

    def _parse_insert(self, stmt: sqlparse.sql.Statement, procedure_name: str = "") -> SQLStatement:
        self._alias_map = {}
        sql_str = str(stmt).strip()

        target_tables = self._extract_insert_target_regex(sql_str)
        source_tables = self._extract_from_tables(stmt)
        column_lineage = self._extract_insert_lineage_regex(sql_str, target_tables)

        return SQLStatement(
            stmt_type="INSERT",
            raw_sql=sql_str,
            source_tables=source_tables,
            target_tables=target_tables,
            column_lineage=column_lineage,
            procedure_name=procedure_name,
        )

    def _parse_update(self, stmt: sqlparse.sql.Statement, procedure_name: str = "") -> SQLStatement:
        self._alias_map = {}
        sql_str = str(stmt).strip()

        target_tables = self._extract_update_target_regex(sql_str)
        source_tables = self._extract_from_tables(stmt)
        column_lineage = self._extract_update_lineage_regex(sql_str, target_tables)

        return SQLStatement(
            stmt_type="UPDATE",
            raw_sql=sql_str,
            source_tables=source_tables,
            target_tables=target_tables,
            column_lineage=column_lineage,
            procedure_name=procedure_name,
        )

    def _parse_delete(self, stmt: sqlparse.sql.Statement, procedure_name: str = "") -> SQLStatement:
        self._alias_map = {}
        sql_str = str(stmt).strip()
        target_tables = self._extract_delete_target_regex(sql_str)

        return SQLStatement(
            stmt_type="DELETE",
            raw_sql=sql_str,
            source_tables=[],
            target_tables=target_tables,
            column_lineage=[],
            procedure_name=procedure_name,
        )

    def _extract_insert_target_regex(self, sql: str) -> list[TableReference]:
        match = re.search(r'INSERT\s+INTO\s+(\w+)', sql, re.IGNORECASE)
        if match:
            name = match.group(1)
            return [TableReference(name=name, alias=name)]
        return []

    def _extract_update_target_regex(self, sql: str) -> list[TableReference]:
        match = re.search(r'UPDATE\s+(\w+)', sql, re.IGNORECASE)
        if match:
            name = match.group(1)
            return [TableReference(name=name, alias=name)]
        return []

    def _extract_delete_target_regex(self, sql: str) -> list[TableReference]:
        match = re.search(r'DELETE\s+FROM\s+(\w+)', sql, re.IGNORECASE)
        if match:
            name = match.group(1)
            return [TableReference(name=name, alias=name)]
        return []

    def _extract_from_tables(self, stmt: sqlparse.sql.Statement) -> list[TableReference]:
        tables: list[TableReference] = []
        sql_str = str(stmt)

        from_pattern = r'(?:FROM|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?'
        for match in re.finditer(from_pattern, sql_str, re.IGNORECASE):
            table_name = match.group(1)
            alias = match.group(2) or table_name
            if table_name.upper() in ("SELECT", "WHERE", "SET", "INTO", "ON", "AND", "OR"):
                continue
            if not any(t.name.lower() == table_name.lower() for t in tables):
                self._alias_map[alias.lower()] = table_name
                tables.append(TableReference(name=table_name, alias=alias))

        return tables

    def _extract_select_lineage(self, stmt: sqlparse.sql.Statement,
                                 source_tables: list[TableReference]) -> list[LineageEdge]:
        lineage: list[LineageEdge] = []
        sql_str = str(stmt)

        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_str, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return lineage

        select_clause = select_match.group(1).strip()
        columns = self._split_select_columns(select_clause)

        for col_expr in columns:
            col_expr = col_expr.strip()
            if not col_expr:
                continue

            alias = ""
            as_match = re.search(r'\s+AS\s+(\w+)\s*$', col_expr, re.IGNORECASE)
            if as_match:
                alias = as_match.group(1)
                col_expr = col_expr[:as_match.start()].strip()
            else:
                parts = col_expr.rsplit(None, 1)
                if len(parts) == 2 and parts[1] not in ("+", "-", "*", "/", "||", "AND", "OR"):
                    if not any(c in parts[0] for c in ("(", ")", "+", "-", "*", "/")):
                        alias = parts[1]
                        col_expr = parts[0]

            target_name = alias if alias else self._extract_column_name(col_expr)
            source_columns = self._resolve_column_sources(col_expr, source_tables)

            transformation = self._detect_transformation(col_expr)

            for src in source_columns:
                lineage.append(LineageEdge(
                    source=src,
                    target=target_name,
                    transformation=transformation,
                    via="",
                ))

            if not source_columns:
                lineage.append(LineageEdge(
                    source=col_expr,
                    target=target_name,
                    transformation=transformation if transformation != "DIRECT" else "EXPRESSION",
                    via="",
                ))

        return lineage

    def _split_select_columns(self, select_clause: str) -> list[str]:
        columns: list[str] = []
        depth = 0
        current = ""

        for char in select_clause:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char == ',' and depth == 0:
                columns.append(current.strip())
                current = ""
                continue
            current += char

        if current.strip():
            columns.append(current.strip())

        return columns

    def _extract_column_name(self, expr: str) -> str:
        if "." in expr:
            parts = expr.split(".")
            return parts[-1].strip()
        return expr.strip()

    def _extract_insert_columns_regex(self, sql: str) -> list[str]:
        match = re.search(r'INSERT\s+INTO\s+\w+\s*\(([^)]+)\)', sql, re.IGNORECASE)
        if match:
            cols_str = match.group(1)
            return [c.strip() for c in cols_str.split(",")]
        return []

    def _extract_insert_lineage_regex(self, sql: str,
                                       target_tables: list[TableReference]) -> list[LineageEdge]:
        lineage: list[LineageEdge] = []
        if not target_tables:
            return lineage

        target_table = target_tables[0]
        insert_columns = self._extract_insert_columns_regex(sql)

        select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return lineage

        select_clause = select_match.group(1).strip()
        select_columns = self._split_select_columns(select_clause)

        source_tables = self._extract_from_tables_sql(sql)

        for i, col_expr in enumerate(select_columns):
            col_expr = col_expr.strip()
            if not col_expr:
                continue

            target_col = insert_columns[i] if i < len(insert_columns) else self._extract_column_name(col_expr)
            target_qualified = f"{target_table.name}.{target_col}"

            source_columns = self._resolve_column_sources(col_expr, source_tables)
            transformation = self._detect_transformation(col_expr)

            for src in source_columns:
                lineage.append(LineageEdge(
                    source=src,
                    target=target_qualified,
                    transformation=transformation,
                    via="INSERT",
                ))

            if not source_columns:
                lineage.append(LineageEdge(
                    source=col_expr,
                    target=target_qualified,
                    transformation=transformation if transformation != "DIRECT" else "EXPRESSION",
                    via="INSERT",
                ))

        return lineage

    def _extract_update_lineage_regex(self, sql: str,
                                       target_tables: list[TableReference]) -> list[LineageEdge]:
        lineage: list[LineageEdge] = []
        if not target_tables:
            return lineage

        target_table = target_tables[0]

        set_match = re.search(r'SET\s+(.*?)(?:\s+WHERE|\s*$)', sql, re.IGNORECASE | re.DOTALL)
        if not set_match:
            return lineage

        set_clause = set_match.group(1).strip()
        assignments = [a.strip() for a in set_clause.split(",")]

        for assignment in assignments:
            if "=" not in assignment:
                continue

            parts = assignment.split("=", 1)
            left = parts[0].strip()
            right = parts[1].strip()

            if "." not in left:
                left = f"{target_table.name}.{left}"

            source_columns = self._extract_column_references(right, target_table.name)
            transformation = self._detect_transformation(right)

            for src in source_columns:
                lineage.append(LineageEdge(
                    source=src,
                    target=left,
                    transformation=transformation,
                    via="UPDATE",
                ))

            if not source_columns:
                lineage.append(LineageEdge(
                    source=right,
                    target=left,
                    transformation="EXPRESSION",
                    via="UPDATE",
                ))

        return lineage

    def _extract_from_tables_sql(self, sql: str) -> list[TableReference]:
        tables: list[TableReference] = []
        from_pattern = r'(?:FROM|JOIN)\s+(\w+)(?:\s+(?:AS\s+)?(\w+))?'
        for match in re.finditer(from_pattern, sql, re.IGNORECASE):
            table_name = match.group(1)
            alias = match.group(2) or table_name
            if table_name.upper() in ("SELECT", "WHERE", "SET", "INTO", "ON", "AND", "OR"):
                continue
            if not any(t.name.lower() == table_name.lower() for t in tables):
                self._alias_map[alias.lower()] = table_name
                tables.append(TableReference(name=table_name, alias=alias))
        return tables

    def _resolve_column_sources(self, expr: str, source_tables: list[TableReference]) -> list[str]:
        sources: list[str] = []

        dotted_refs = re.findall(r'(\w+)\.(\w+)', expr)
        for alias_or_table, column in dotted_refs:
            real_table = self._alias_map.get(alias_or_table.lower(), alias_or_table)
            sources.append(f"{real_table}.{column}")

        if sources:
            return sources

        if expr.strip() == "*":
            for table in source_tables:
                sources.append(f"{table.name}.*")
            return sources

        return sources

    def _detect_transformation(self, expr: str) -> str:
        expr_upper = expr.upper()
        if any(func in expr_upper for func in ("SUM(", "COUNT(", "AVG(", "MIN(", "MAX(")):
            return "AGGREGATION"
        if "CASE" in expr_upper:
            return "CONDITIONAL"
        if any(op in expr for op in ("+", "-", "*", "/")):
            return "ARITHMETIC"
        if "||" in expr or "CONCAT" in expr_upper:
            return "CONCATENATION"
        if any(func in expr_upper for func in ("COALESCE(", "NVL(", "ISNULL(")):
            return "NULL_HANDLING"
        if "CAST" in expr_upper or "::" in expr:
            return "TYPE_CAST"
        if len(expr.split(".")) == 2 and "(" not in expr:
            return "DIRECT"
        return "DIRECT"

    def _extract_column_references(self, expr: str, exclude_table: str = "") -> list[str]:
        refs: list[str] = []
        dotted = re.findall(r'(\w+)\.(\w+)', expr)
        for alias_or_table, column in dotted:
            real_table = self._alias_map.get(alias_or_table.lower(), alias_or_table)
            if real_table.lower() != exclude_table.lower():
                refs.append(f"{real_table}.{column}")
        return refs

    def extract_tables_from_sql(self, sql: str) -> list[Node]:
        nodes: list[Node] = []
        seen: set[str] = set()
        statements = self.parse(sql)

        for stmt in statements:
            for table in stmt.source_tables + stmt.target_tables:
                if table.name.lower() not in seen:
                    seen.add(table.name.lower())
                    nodes.append(Node(
                        id=f"table_{table.name.lower()}",
                        type=NodeType.TABLE,
                        name=table.name,
                        qualified_name=table.name,
                        metadata={"alias": table.alias},
                    ))

        return nodes

    def extract_procedures_from_sql(self, sql: str) -> list[Node]:
        nodes: list[Node] = []
        patterns = [
            r"(?:CREATE|ALTER)\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+(\w+)",
            r"(?:CREATE|ALTER)\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+(\w+)",
        ]
        seen: set[str] = set()

        for pattern in patterns:
            for match in re.finditer(pattern, sql, re.IGNORECASE):
                name = match.group(1)
                if name.lower() not in seen:
                    seen.add(name.lower())
                    nodes.append(Node(
                        id=f"proc_{name.lower()}",
                        type=NodeType.PROCEDURE,
                        name=name,
                        qualified_name=name,
                        source_code=sql,
                    ))

        return nodes
