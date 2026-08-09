from __future__ import annotations

from app.core.commands.command import Command
from app.core.services.annotation_service import AnnotationService


class AddMarkupAnnotationCommand(Command):
    def __init__(
        self,
        service: AnnotationService,
        document,
        page_index: int,
        kind: str,
        visual_rects: tuple[tuple[float, float, float, float], ...],
        selected_text: str,
        color: tuple[float, float, float],
        opacity: float = 0.45,
    ) -> None:
        self.description = f"Add {kind.title()}"
        self._service = service
        self._document = document
        self._page_index = page_index
        self._kind = kind
        self._visual_rects = visual_rects
        self._selected_text = selected_text
        self._color = color
        self._opacity = opacity
        self.xref: int | None = None

    def do(self) -> None:
        self.xref = self._service.add_markup(
            self._document,
            self._page_index,
            self._kind,
            self._visual_rects,
            self._selected_text,
            self._color,
            self._opacity,
        )

    def undo(self) -> None:
        if self.xref is None:
            return
        self._service.delete_annotation(self._document, self._page_index, self.xref)
        self.xref = None