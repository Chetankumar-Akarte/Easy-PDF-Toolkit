from __future__ import annotations

from pathlib import Path


class DocumentService:
    """Coordinates open, save, export, and dirty-state transitions."""

    def open(self, path: str) -> None:
        _ = path

    def save(self, document, current_path: str, target_path: str | None = None) -> str:
        destination = Path(target_path or current_path).expanduser().resolve()
        current = Path(current_path).expanduser().resolve()

        if destination == current:
            # Saving back to the same file requires incremental write in PyMuPDF.
            document.saveIncr()
            return str(current)

        destination.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(destination), garbage=3, deflate=True)
        return str(destination)
