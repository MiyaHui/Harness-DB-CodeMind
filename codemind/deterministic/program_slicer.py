from __future__ import annotations

import re
from typing import Any, Optional

from codemind.core.models import Edge, EdgeType, Graph, Node, NodeType


class ProgramSlicer:
    def __init__(self, graph: Graph) -> None:
        self.graph = graph

    def slice_forward(self, node_id: str, max_depth: int = 5) -> Graph:
        visited: set[str] = set()
        result_nodes: list[Node] = []
        result_edges: list[Edge] = []

        queue: list[tuple[str, int]] = [(node_id, 0)]
        visited.add(node_id)

        while queue:
            current_id, depth = queue.pop(0)
            if depth > max_depth:
                continue

            node = self.graph.get_node(current_id)
            if node:
                result_nodes.append(node)

            for edge in self.graph.get_outgoing_edges(current_id):
                result_edges.append(edge)
                if edge.target_id not in visited:
                    visited.add(edge.target_id)
                    queue.append((edge.target_id, depth + 1))

        return Graph(nodes=result_nodes, edges=result_edges)

    def slice_backward(self, node_id: str, max_depth: int = 5) -> Graph:
        visited: set[str] = set()
        result_nodes: list[Node] = []
        result_edges: list[Edge] = []

        queue: list[tuple[str, int]] = [(node_id, 0)]
        visited.add(node_id)

        while queue:
            current_id, depth = queue.pop(0)
            if depth > max_depth:
                continue

            node = self.graph.get_node(current_id)
            if node:
                result_nodes.append(node)

            for edge in self.graph.get_incoming_edges(current_id):
                result_edges.append(edge)
                if edge.source_id not in visited:
                    visited.add(edge.source_id)
                    queue.append((edge.source_id, depth + 1))

        return Graph(nodes=result_nodes, edges=result_edges)

    def slice_bidirectional(self, node_id: str, max_depth: int = 5) -> Graph:
        forward = self.slice_forward(node_id, max_depth)
        backward = self.slice_backward(node_id, max_depth)

        node_ids = {n.id for n in forward.nodes} | {n.id for n in backward.nodes}
        return self.graph.subgraph(node_ids)

    def slice_by_criteria(self, node_ids: list[str], direction: str = "forward",
                           max_depth: int = 5) -> Graph:
        combined_nodes: set[str] = set()
        combined_edges: list[Edge] = []

        for node_id in node_ids:
            if direction == "forward":
                sub = self.slice_forward(node_id, max_depth)
            elif direction == "backward":
                sub = self.slice_backward(node_id, max_depth)
            else:
                sub = self.slice_bidirectional(node_id, max_depth)

            combined_nodes.update(n.id for n in sub.nodes)
            combined_edges.extend(sub.edges)

        return self.graph.subgraph(combined_nodes)

    def slice_by_type(self, node_type: NodeType) -> Graph:
        nodes = [n for n in self.graph.nodes if n.type == node_type]
        node_ids = {n.id for n in nodes}
        edges = [e for e in self.graph.edges if e.source_id in node_ids or e.target_id in node_ids]
        return Graph(nodes=nodes, edges=edges)

    def get_dependency_chain(self, node_id: str) -> list[list[str]]:
        chains: list[list[str]] = []
        self._dfs_chains(node_id, [], chains, set())
        return chains

    def _dfs_chains(self, current_id: str, path: list[str],
                     chains: list[list[str]], visited: set[str]) -> None:
        if current_id in visited:
            chains.append(path + [current_id])
            return

        visited.add(current_id)
        path.append(current_id)

        outgoing = self.graph.get_outgoing_edges(current_id)
        if not outgoing:
            chains.append(path[:])
        else:
            for edge in outgoing:
                self._dfs_chains(edge.target_id, path, chains, visited.copy())

        path.pop()
