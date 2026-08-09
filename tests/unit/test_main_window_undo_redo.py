from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication

from app.infra.storage.recent_files_repo import RecentFilesRepository
from app.infra.storage.settings_repo import SettingsRepository
from app.ui.main_window import MainWindow


def _create_pdf(path: Path) -> None:
    document = fitz.open()
    try:
        document.new_page()
        document.save(path)
    finally:
        document.close()


def test_command_history_is_isolated_per_document_tab(tmp_path: Path) -> None:
    first_path = tmp_path / "first.pdf"
    second_path = tmp_path / "second.pdf"
    _create_pdf(first_path)
    _create_pdf(second_path)

    QApplication.instance() or QApplication([])
    window = MainWindow(SettingsRepository(tmp_path), RecentFilesRepository(tmp_path))
    window._open_document_by_path(str(first_path))
    first_index = window.tab_widget.currentIndex()
    first_session = window._current_session()
    assert first_session is not None

    window._rotate_current_page_right()
    assert first_session.document[0].rotation == 90
    assert window.undo_action.text() == "Undo Rotate Page 1"

    window._open_document_by_path(str(second_path))
    assert not window.undo_action.isEnabled()
    assert not window.redo_action.isEnabled()

    window.tab_widget.setCurrentIndex(first_index)
    assert window.undo_action.isEnabled()
    window.undo_action.trigger()
    assert first_session.document[0].rotation == 0
    assert window.redo_action.isEnabled()