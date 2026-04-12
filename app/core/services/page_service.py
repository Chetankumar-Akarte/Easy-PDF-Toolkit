from __future__ import annotations


class PageService:
    """PDF page mutation operations — rotate, delete, reorder."""

    def rotate_page(self, document, page_index: int, degrees: int) -> None:
        """Rotate a single page by the given degrees (cumulative, snaps to 0/90/180/270)."""
        page = document[page_index]
        new_rotation = (page.rotation + degrees) % 360
        page.set_rotation(new_rotation)

    def delete_page(self, document, page_index: int) -> None:
        """Delete the page at the given index."""
        document.delete_page(page_index)

    def reorder_pages(self, document, new_order: list[int]) -> None:
        """Reorder document pages using a list of current-state page indices in desired order."""
        document.select(new_order)
