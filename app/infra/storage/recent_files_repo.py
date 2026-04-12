from __future__ import annotations

import json
from pathlib import Path


class RecentFilesRepository:
    def __init__(self, workspace_root: Path, max_items: int = 10) -> None:
        self._recent_path = workspace_root / ".easy_pdf_toolkit" / "recent_files.json"
        self._max_items = max_items

    def load(self) -> list[str]:
        if not self._recent_path.exists():
            return []
        items = json.loads(self._recent_path.read_text(encoding="utf-8"))
        # Deduplicate while preserving insertion order (case-insensitive for Windows paths).
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            key = item.lower()
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def add(self, path: str) -> None:
        resolved = str(Path(path).resolve())
        lower = resolved.lower()
        current = [item for item in self.load() if item.lower() != lower]
        current.insert(0, resolved)
        self._write(current[: self._max_items])

    def remove(self, path: str) -> None:
        lower = str(Path(path).resolve()).lower()
        current = [item for item in self.load() if item.lower() != lower]
        self._write(current)

    def clear(self) -> None:
        self._write([])

    def _write(self, items: list[str]) -> None:
        self._recent_path.parent.mkdir(parents=True, exist_ok=True)
        self._recent_path.write_text(json.dumps(items, indent=2), encoding="utf-8")
