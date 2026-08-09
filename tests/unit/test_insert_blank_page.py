from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pytest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

import app.ui.main_window as main_window_module
from app.infra.storage.recent_files_repo import RecentFilesRepository
from app.infra.storage.settings_repo import SettingsRepository
from app.ui.dialogs import InsertBlankPageDialog, InsertBlankPageRequest
from app.ui.main_window import MainWindow
from app.ui.theme import get_theme


def test_insert_dialog_maps_position_size_orientation_and_count() -> None:
    app = QApplication.instance() or QApplication([])
    dialog = InsertBlankPageDialog(2, 5, (612, 792), get_theme("light"))

    default_request = dialog.build_request()
    assert default_request == InsertBlankPageRequest(3, 612, 792, 1)
    assert dialog.preview_label.text() == "1 blank page · 612 × 792 pt after Page 3"

    dialog.position_combo.setCurrentText("Before current page")
    dialog.size_combo.setCurrentText("A4")
    dialog.orientation_combo.setCurrentText("Landscape")
    dialog.count_spin.setValue(3)

    assert dialog.build_request() == InsertBlankPageRequest(2, 842, 595, 3)
    assert dialog.preview_label.text() == "3 blank pages · 842 × 595 pt before Page 3"
    app.processEvents()


def test_insert_dialog_uses_uncommitted_page_field_as_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "reference.pdf"
    document = fitz.open()
    try:
        for page_number in range(5):
            document.new_page().insert_text((20, 30), f"page {page_number + 1}")
        document.save(pdf_path)
    finally:
        document.close()

    captured: dict[str, int] = {}

    class RejectedDialog:
        def __init__(self, **kwargs) -> None:
            captured["current_page"] = kwargs["current_page"]

        def exec(self):
            return QDialog.DialogCode.Rejected

    QApplication.instance() or QApplication([])
    window = MainWindow(SettingsRepository(tmp_path), RecentFilesRepository(tmp_path))
    window._open_document_by_path(str(pdf_path))
    monkeypatch.setattr(main_window_module, "InsertBlankPageDialog", RejectedDialog)

    window.page_spin.lineEdit().setText("5")
    window.insert_blank_page_action.trigger()

    session = window._current_session()
    assert session is not None
    assert captured["current_page"] == 4
    assert session.current_page == 4


def test_insert_workflow_rebuilds_marks_dirty_saves_and_protects_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "insert.pdf"
    document = fitz.open()
    try:
        document.new_page(width=300, height=400).insert_text((20, 30), "first")
        document.new_page(width=500, height=600).insert_text((20, 30), "second")
        document.save(pdf_path)
    finally:
        document.close()

    class AcceptedDialog:
        def __init__(self, **_kwargs) -> None:
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def build_request(self) -> InsertBlankPageRequest:
            return InsertBlankPageRequest(1, 612, 792, 2)

    app = QApplication.instance() or QApplication([])
    window = MainWindow(SettingsRepository(tmp_path), RecentFilesRepository(tmp_path))
    window._open_document_by_path(str(pdf_path))
    monkeypatch.setattr(main_window_module, "InsertBlankPageDialog", AcceptedDialog)

    assert window.insert_blank_page_action.isEnabled()
    assert not window.insert_blank_page_action.icon().isNull()
    assert window.insert_blank_page_action.shortcut().toString() == "Ctrl+Shift+B"

    window._open_insert_blank_page_dialog()

    session = window._current_session()
    assert session is not None
    assert session.page_count == 4
    assert session.current_page == 1
    assert session.document[0].get_text().strip() == "first"
    assert session.document[3].get_text().strip() == "second"
    assert session.document[1].rect.width == pytest.approx(612)
    assert session.document[1].rect.height == pytest.approx(792)
    assert window.thumbnail_list.count() == 4
    assert session.render_queue[0] == 1
    assert session.is_dirty
    assert window.tab_widget.tabText(window.tab_widget.currentIndex()).endswith(" *")

    assert window._save_session(session)
    assert not session.is_dirty
    saved = fitz.open(pdf_path)
    try:
        assert saved.page_count == 4
    finally:
        saved.close()

    session.is_dirty = True
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Cancel,
    )
    assert not window._confirm_close_session(session)
    assert not window._close_tab(window.tab_widget.currentIndex())
    assert window._current_session() is session
    app.processEvents()