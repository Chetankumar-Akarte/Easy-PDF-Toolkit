from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QSignalSpy, QTest
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


def test_text_selection_paints_and_clears_without_mutating_source() -> None:
    QApplication.instance() or QApplication([])
    canvas = PdfCanvas()
    image = QImage(100, 100, QImage.Format.Format_RGB888)
    image.fill(QColor("white"))
    canvas.set_document_pages([image])

    canvas.set_text_selection(0, [(0.1, 0.1, 0.4, 0.3)])
    selected_pixmap = canvas._page_labels[0].pixmap()
    assert selected_pixmap is not None
    assert selected_pixmap.toImage().pixelColor(20, 20) != QColor("white")
    assert image.pixelColor(20, 20) == QColor("white")

    canvas.clear_text_selection()
    cleared_pixmap = canvas._page_labels[0].pixmap()
    assert cleared_pixmap is not None
    assert cleared_pixmap.toImage().pixelColor(20, 20) == QColor("white")


def test_text_selection_mode_emits_normalized_mouse_drag() -> None:
    app = QApplication.instance() or QApplication([])
    canvas = PdfCanvas()
    canvas.set_document_pages([QImage(100, 100, QImage.Format.Format_RGB888)])
    canvas.set_text_selection_enabled(True)
    canvas.show()
    app.processEvents()

    label = canvas._page_labels[0]
    spy = QSignalSpy(canvas.text_selection_requested)
    QTest.mousePress(label, Qt.MouseButton.LeftButton, pos=QPoint(10, 20))
    QTest.mouseMove(label, QPoint(50, 60))
    QTest.mouseRelease(label, Qt.MouseButton.LeftButton, pos=QPoint(50, 60))

    assert spy.count() == 1
    arguments = spy.at(0)
    assert arguments[0] == 0
    assert arguments[1:] == [0.1, 0.2, 0.5, 0.6]