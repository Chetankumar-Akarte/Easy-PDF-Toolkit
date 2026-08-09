from __future__ import annotations

from app.core.commands.command import Command
from app.core.services.page_service import PageService


class RotatePageCommand(Command):
    def __init__(self, service: PageService, document, page_index: int, degrees: int) -> None:
        self.description = f"Rotate Page {page_index + 1}"
        self._service = service
        self._document = document
        self._page_index = page_index
        self._degrees = degrees

    def do(self) -> None:
        self._service.rotate_page(self._document, self._page_index, self._degrees)

    def undo(self) -> None:
        self._service.rotate_page(self._document, self._page_index, -self._degrees)


class InsertBlankPagesCommand(Command):
    def __init__(
        self,
        service: PageService,
        document,
        insertion_index: int,
        width: float,
        height: float,
        count: int,
    ) -> None:
        page_word = "Page" if count == 1 else "Pages"
        self.description = f"Insert {count} Blank {page_word}"
        self._service = service
        self._document = document
        self._insertion_index = insertion_index
        self._width = width
        self._height = height
        self._count = count
        self._toc_before: list[list] | None = None
        self._toc_after: list[list] | None = None

    def do(self) -> None:
        if self._toc_before is None:
            self._toc_before = self._document.get_toc(simple=False)
        self._service.insert_blank_pages(
            self._document,
            self._insertion_index,
            self._width,
            self._height,
            self._count,
        )
        if self._toc_after is None:
            self._toc_after = self._document.get_toc(simple=False)
        elif self._toc_after:
            self._document.set_toc(self._toc_after)

    def undo(self) -> None:
        self._document.delete_pages(
            self._insertion_index,
            self._insertion_index + self._count - 1,
        )
        if self._toc_before:
            self._document.set_toc(self._toc_before)


class DeletePageCommand(Command):
    def __init__(self, service: PageService, document, page_index: int) -> None:
        import fitz

        self.description = f"Delete Page {page_index + 1}"
        self._service = service
        self._document = document
        self._page_index = page_index
        self._toc_before = document.get_toc(simple=False)
        self._toc_after: list[list] | None = None
        snapshot = fitz.open()
        try:
            snapshot.insert_pdf(document, from_page=page_index, to_page=page_index)
            self._page_snapshot = snapshot.tobytes(garbage=3, deflate=True)
        finally:
            snapshot.close()

    def do(self) -> None:
        self._service.delete_page(self._document, self._page_index)
        if self._toc_after is None:
            self._toc_after = self._document.get_toc(simple=False)
        elif self._toc_after:
            self._document.set_toc(self._toc_after)

    def undo(self) -> None:
        import fitz

        snapshot = fitz.open(stream=self._page_snapshot, filetype="pdf")
        try:
            self._document.insert_pdf(snapshot, start_at=self._page_index)
        finally:
            snapshot.close()
        if self._toc_before:
            self._document.set_toc(self._toc_before)


class ReorderPagesCommand(Command):
    def __init__(self, service: PageService, document, new_order: list[int]) -> None:
        self.description = "Reorder Pages"
        self._service = service
        self._document = document
        self._new_order = list(new_order)
        self._inverse_order = [self._new_order.index(index) for index in range(len(new_order))]
        self._toc_before = document.get_toc(simple=False)
        self._toc_after: list[list] | None = None

    def do(self) -> None:
        self._service.reorder_pages(self._document, self._new_order)
        if self._toc_after is None:
            self._toc_after = self._document.get_toc(simple=False)
        elif self._toc_after:
            self._document.set_toc(self._toc_after)

    def undo(self) -> None:
        self._service.reorder_pages(self._document, self._inverse_order)
        if self._toc_before:
            self._document.set_toc(self._toc_before)