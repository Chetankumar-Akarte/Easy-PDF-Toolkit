from dataclasses import dataclass, field


@dataclass
class DocumentState:
    path: str | None = None
    page_count: int = 0
    is_dirty: bool = False
    selected_pages: list[int] = field(default_factory=list)
