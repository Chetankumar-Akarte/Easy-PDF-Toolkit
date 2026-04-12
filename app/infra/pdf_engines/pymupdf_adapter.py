from __future__ import annotations

from PySide6.QtGui import QImage


class PyMuPDFAdapter:
    """Thin wrapper for PyMuPDF operations."""

    def open_document(self, path: str):
        import fitz

        return fitz.open(path)

    def close_document(self, document) -> None:
        document.close()

    def page_count(self, document) -> int:
        return document.page_count

    def page_sizes(self, document) -> list[tuple[int, int]]:
        sizes: list[tuple[int, int]] = []
        for page_index in range(document.page_count):
            rect = document.load_page(page_index).rect
            sizes.append((max(int(rect.width), 1), max(int(rect.height), 1)))
        return sizes

    def render_page(
        self,
        document,
        page_index: int,
        zoom: float = 1.0,
        rotation_degrees: int = 0,
        invert_colors: bool = False,
        dpr: float = 1.0,
    ) -> QImage:
        import fitz

        page = document.load_page(page_index)
        matrix = fitz.Matrix(zoom * dpr, zoom * dpr).prerotate(rotation_degrees)
        pix = page.get_pixmap(matrix=matrix, alpha=False, annots=False)
        if invert_colors:
            pix.invert_irect()
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        copied = image.copy()
        copied.setDevicePixelRatio(dpr)
        return copied
