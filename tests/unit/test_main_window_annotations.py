from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication

from app.core.services.annotation_service import AnnotationService
from app.infra.storage.recent_files_repo import RecentFilesRepository
from app.infra.storage.settings_repo import SettingsRepository
from app.ui.main_window import MainWindow


def test_text_selection_markup_undo_redo_and_save(tmp_path: Path) -> None:
    pdf_path = tmp_path / "annotations.pdf"
    document = fitz.open()
    try:
        document.new_page(width=400, height=300).insert_text((50, 80), "Alpha Beta")
        document.save(pdf_path)
    finally:
        document.close()

    app = QApplication.instance() or QApplication([])
    window = MainWindow(SettingsRepository(tmp_path), RecentFilesRepository(tmp_path))
    window._open_document_by_path(str(pdf_path))
    session = window._current_session()
    assert session is not None

    window.select_text_action.setChecked(True)
    assert session.canvas._selection_enabled
    assert not window.highlight_action.isEnabled()

    word = session.document[0].get_text("words", sort=True)[1]
    visual_word = fitz.Rect(word[:4]) * session.document[0].rotation_matrix
    page_rect = session.document[0].rect
    session.canvas.text_selection_requested.emit(
        0,
        visual_word.x0 / page_rect.width,
        visual_word.y0 / page_rect.height,
        visual_word.x1 / page_rect.width,
        visual_word.y1 / page_rect.height,
    )
    app.processEvents()

    assert session.text_selection is not None
    assert session.text_selection.text == "Beta"
    assert window.highlight_action.isEnabled()
    assert window.toggle_properties_action.isChecked()
    assert not window.properties_panel.isHidden()
    assert "Page 1" in window.properties_panel.selection_type_label.text()
    assert "Beta" in window.properties_panel.selection_details_label.text()

    window.highlight_action.trigger()
    assert session.text_selection is None
    assert not window.highlight_action.isEnabled()
    annotations = window.annotation_service.list_annotations(session.document)
    assert len(annotations) == 1
    assert annotations[0].kind == AnnotationService.HIGHLIGHT
    assert session.is_dirty
    assert window.undo_action.text() == "Undo Add Highlight"

    window.undo_action.trigger()
    assert window.annotation_service.list_annotations(session.document) == []
    assert not session.is_dirty
    window.redo_action.trigger()
    assert len(window.annotation_service.list_annotations(session.document)) == 1
    assert session.is_dirty

    assert window._save_session(session)
    assert not session.is_dirty
    session.document.reload_page(session.document[0])
    app.processEvents()

    reopened = fitz.open(pdf_path)
    try:
        assert len(AnnotationService().list_annotations(reopened)) == 1
    finally:
        reopened.close()