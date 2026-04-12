from dataclasses import dataclass


@dataclass
class AppState:
    active_document_path: str | None = None
    zoom_level: float = 1.0
    selected_page_index: int = 0
    active_tool: str = "select"
