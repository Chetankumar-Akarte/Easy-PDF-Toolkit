from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from app.ui.widgets.pdf_canvas import PdfCanvas


def test_search_highlight_paints_and_clears_without_mutating_source() -> None:
    app = QApplication.instance() or QApplication([])
    canvas = PdfCanvas()
    image = QImage(100, 100, QImage.Format.Format_RGB888)
    image.fill(QColor("white"))
    canvas.set_document_pages([image])

    match_rect = (0.1, 0.1, 0.4, 0.3)
    canvas.set_search_highlights({0: [match_rect]}, (0, match_rect))

    highlighted_pixmap = canvas._page_labels[0].pixmap()
    assert highlighted_pixmap is not None
    highlighted = highlighted_pixmap.toImage().pixelColor(20, 20)
    blank = highlighted_pixmap.toImage().pixelColor(80, 80)
    assert highlighted != blank

    canvas.set_search_highlights({}, None)
    cleared_pixmap = canvas._page_labels[0].pixmap()
    assert cleared_pixmap is not None
    assert cleared_pixmap.toImage().pixelColor(20, 20) == blank
    app.processEvents()