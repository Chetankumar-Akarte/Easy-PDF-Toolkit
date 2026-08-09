from __future__ import annotations

from app.core.commands.command import Command
from app.core.services.annotation_service import AnnotationInfo, AnnotationService


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


class AddStickyNoteAnnotationCommand(Command):
    def __init__(
        self,
        service: AnnotationService,
        document,
        page_index: int,
        x_ratio: float,
        y_ratio: float,
        content: str,
        color: tuple[float, float, float] = (1.0, 0.86, 0.2),
        opacity: float = 0.95,
    ) -> None:
        self.description = "Add Sticky Note"
        self._service = service
        self._document = document
        self._page_index = page_index
        self._x_ratio = x_ratio
        self._y_ratio = y_ratio
        self._content = content
        self._color = color
        self._opacity = opacity
        self.xref: int | None = None

    def do(self) -> None:
        self.xref = self._service.add_sticky_note(
            self._document,
            self._page_index,
            self._x_ratio,
            self._y_ratio,
            self._content,
            self._color,
            self._opacity,
        )

    def undo(self) -> None:
        if self.xref is None:
            return
        self._service.delete_annotation(self._document, self._page_index, self.xref)
        self.xref = None


class EditStickyNoteCommand(Command):
    def __init__(
        self,
        service: AnnotationService,
        document,
        annotation: AnnotationInfo,
        new_content: str,
    ) -> None:
        self.description = "Edit Sticky Note"
        self._service = service
        self._document = document
        self._page_index = annotation.page_index
        self.xref = annotation.xref
        self._old_content = annotation.content
        self._new_content = new_content

    def do(self) -> None:
        self._service.update_annotation_content(
            self._document,
            self._page_index,
            self.xref,
            self._new_content,
        )

    def undo(self) -> None:
        self._service.update_annotation_content(
            self._document,
            self._page_index,
            self.xref,
            self._old_content,
        )


class DeleteAnnotationCommand(Command):
    def __init__(
        self,
        service: AnnotationService,
        document,
        annotation: AnnotationInfo,
    ) -> None:
        self.description = f"Delete {annotation.kind.title()}"
        self._service = service
        self._document = document
        self._annotation = annotation
        self.xref: int | None = annotation.xref

    def do(self) -> None:
        if self.xref is None:
            raise ValueError("Annotation no longer exists.")
        self._service.delete_annotation(
            self._document,
            self._annotation.page_index,
            self.xref,
        )
        self.xref = None

    def undo(self) -> None:
        self.xref = self._service.restore_annotation(self._document, self._annotation)