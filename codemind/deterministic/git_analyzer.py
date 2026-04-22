import os
import re
from dataclasses import dataclass, field
from typing import Optional

from codemind.core.models import Edge, EdgeType, Node, NodeType


@dataclass
class GitChange:
    file_path: str
    change_type: str
    added_lines: int = 0
    removed_lines: int = 0
    author: str = ""
    message: str = ""
    timestamp: str = ""


class GitAnalyzer:
    def __init__(self, repo_path: str) -> None:
        self.repo_path = repo_path

    def analyze(self) -> list[GitChange]:
        changes: list[GitChange] = []
        if not os.path.isdir(os.path.join(self.repo_path, ".git")):
            return changes

        try:
            log_output = self._run_git_command(
                f'git -C "{self.repo_path}" log --pretty=format:%H --name-status --diff-filter=AMDR -50'
            )
            changes = self._parse_git_log(log_output)
        except Exception:
            pass

        return changes

    def get_change_frequency(self) -> dict[str, int]:
        frequency: dict[str, int] = {}
        changes = self.analyze()
        for change in changes:
            key = change.file_path
            frequency[key] = frequency.get(key, 0) + 1
        return frequency

    def get_hotspots(self, threshold: int = 3) -> list[tuple[str, int]]:
        freq = self.get_change_frequency()
        hotspots = [(path, count) for path, count in freq.items() if count >= threshold]
        return sorted(hotspots, key=lambda x: x[1], reverse=True)

    def get_recent_changes(self, days: int = 30) -> list[GitChange]:
        changes = self.analyze()
        return changes

    def _run_git_command(self, command: str) -> str:
        import subprocess
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=30
        )
        return result.stdout

    def _parse_git_log(self, log_output: str) -> list[GitChange]:
        changes: list[GitChange] = []
        if not log_output.strip():
            return changes

        current_hash = ""
        for line in log_output.split("\n"):
            line = line.strip()
            if not line:
                continue
            if re.match(r'^[a-f0-9]{40}$', line):
                current_hash = line
                continue
            if "\t" in line:
                parts = line.split("\t")
                if len(parts) >= 2:
                    change_type = parts[0].strip()
                    file_path = parts[1].strip()
                    changes.append(GitChange(
                        file_path=file_path,
                        change_type=change_type,
                    ))

        return changes
