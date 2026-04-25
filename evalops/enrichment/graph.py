from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GraphIndex:
    nodes_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)
    files_by_id: dict[str, str] = field(default_factory=dict)
    neighbors_by_file: dict[str, set[str]] = field(default_factory=dict)

    @classmethod
    def from_graph_dir(cls, graph_dir: Path | None) -> "GraphIndex":
        if graph_dir is None:
            return cls()
        graph_file = graph_dir / "graph.json"
        if not graph_file.exists():
            return cls()
        try:
            payload = json.loads(graph_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: Any) -> "GraphIndex":
        index = cls()
        nodes = payload.get("nodes", []) if isinstance(payload, dict) else []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or node.get("name") or "")
            file_path = _node_file(node)
            if not node_id or not file_path:
                continue
            normalized = _normalize_file(file_path)
            index.nodes_by_id[node_id] = node
            index.files_by_id[node_id] = normalized
            index.neighbors_by_file.setdefault(normalized, set())

        edges = payload.get("edges", []) if isinstance(payload, dict) else []
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("source") or edge.get("from") or "")
            target = str(edge.get("target") or edge.get("to") or "")
            source_file = index.files_by_id.get(source)
            target_file = index.files_by_id.get(target)
            if not source_file or not target_file or source_file == target_file:
                continue
            index.neighbors_by_file.setdefault(source_file, set()).add(target_file)
            index.neighbors_by_file.setdefault(target_file, set()).add(source_file)
        return index

    def neighborhood(self, seed_file: str, max_hops: int = 1, max_files: int = 20) -> list[str]:
        seed = _normalize_file(seed_file)
        seen = {seed}
        frontier = {seed}
        ordered: list[str] = []
        for _ in range(max(0, max_hops)):
            next_frontier: set[str] = set()
            for file_path in sorted(frontier):
                for neighbor in sorted(self.neighbors_by_file.get(file_path, set())):
                    if neighbor in seen:
                        continue
                    seen.add(neighbor)
                    ordered.append(neighbor)
                    next_frontier.add(neighbor)
                    if len(ordered) >= max_files:
                        return ordered
            frontier = next_frontier
            if not frontier:
                break
        return ordered

    def describe_neighborhood(self, seed_files: list[str], max_hops: int, max_files: int) -> str:
        lines: list[str] = []
        for seed in seed_files:
            neighbors = self.neighborhood(seed, max_hops=max_hops, max_files=max_files)
            if neighbors:
                lines.append(f"{seed} -> {', '.join(neighbors)}")
            else:
                lines.append(f"{seed} -> [no graph neighbors found]")
        return "\n".join(lines)


def _node_file(node: dict[str, Any]) -> str:
    for key in ("file", "file_path", "path", "filepath"):
        if node.get(key):
            return str(node[key])
    return ""


def _normalize_file(file_path: str) -> str:
    return file_path.removeprefix("a/").removeprefix("b/").replace("\\", "/")
