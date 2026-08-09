from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication, QTabBar, QToolButton

from app.infra.storage.recent_files_repo import RecentFilesRepository
from app.infra.storage.settings_repo import SettingsRepository
from app.ui.main_window import MainWindow


def test_single_document_has_persistent_close_button(tmp_path: Path) -> None:
    pdf_path = tmp_path / "single.pdf"
    document = fitz.open()
    try:
        document.new_page()
        document.save(pdf_path)
    finally:
        document.close()

    app = QApplication.instance() or QApplication([])
    window = MainWindow(SettingsRepository(tmp_path), RecentFilesRepository(tmp_path))

    assert not window.document_close_button.isEnabled()
    assert not window.document_close_button.icon().isNull()
    assert window.document_close_button.toolTip() == "Close current document (Ctrl+Shift+W)"

    window._open_document_by_path(str(pdf_path))

    assert window.document_close_button.isEnabled()
    assert window._current_session() is not None
    tab_close_button = window.tab_widget.tabBar().tabButton(
        window.tab_widget.currentIndex(),
        QTabBar.ButtonPosition.RightSide,
    )
    assert isinstance(tab_close_button, QToolButton)
    assert not tab_close_button.icon().isNull()
    assert tab_close_button.iconSize().width() == 16
    close_image = tab_close_button.icon().pixmap(16, 16).toImage()
    assert any(
        close_image.pixelColor(x, y).alpha() > 0
        for x in range(close_image.width())
        for y in range(close_image.height())
    )

    tab_close_button.click()
    app.processEvents()

    assert window._current_session() is None
    assert window.tab_widget.count() == 1
    assert window.tab_widget.tabText(0) == "Welcome"
    assert not window.document_close_button.isEnabled()