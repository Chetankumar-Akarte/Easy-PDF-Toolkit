from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pytest
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox

from app.core.services.annotation_service import AnnotationService
from app.infra.storage.recent_files_repo import RecentFilesRepository
from app.infra.storage.settings_repo import SettingsRepository
from app.ui.main_window import MainWindow


def test_text_selection_markup_delete_undo_redo_and_save(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    annotation = window.annotation_service.list_annotations(session.document)[0]
    center_x = (annotation.rects[0][0] + annotation.rects[0][2]) / 2
    center_y = (annotation.rects[0][1] + annotation.rects[0][3]) / 2
    window.select_annotation_action.setChecked(True)
    assert not window.select_text_action.isChecked()
    session.canvas.annotation_selection_requested.emit(0, center_x, center_y)
    app.processEvents()

    assert session.annotation_selection is not None
    assert session.annotation_selection.xref == annotation.xref
    assert window.delete_annotation_action.isEnabled()
    assert "Highlight annotation" in window.properties_panel.selection_type_label.text()
    assert session.canvas._annotation_selection is not None

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    window.delete_annotation_action.trigger()
    assert window.annotation_service.list_annotations(session.document) == []
    assert session.annotation_selection is None
    assert window.undo_action.text() == "Undo Delete Highlight"

    window.undo_action.trigger()
    assert len(window.annotation_service.list_annotations(session.document)) == 1
    window.redo_action.trigger()
    assert window.annotation_service.list_annotations(session.document) == []

    assert window._save_session(session)
    assert not session.is_dirty
    session.document.reload_page(session.document[0])
    app.processEvents()

    reopened = fitz.open(pdf_path)
    try:
        assert AnnotationService().list_annotations(reopened) == []
    finally:
        reopened.close()


def test_sticky_note_end_to_end_with_edit_delete_and_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "sticky_notes.pdf"
    document = fitz.open()
    try:
        document.new_page(width=420, height=320).insert_text((50, 70), "Sticky note test")
        document.save(pdf_path)
    finally:
        document.close()

    app = QApplication.instance() or QApplication([])
    window = MainWindow(SettingsRepository(tmp_path), RecentFilesRepository(tmp_path))
    window._open_document_by_path(str(pdf_path))
    session = window._current_session()
    assert session is not None

    text_answers = iter([
        ("First note", True),
        ("Updated note", True),
    ])
    monkeypatch.setattr(
        QInputDialog,
        "getMultiLineText",
        lambda *_args, **_kwargs: next(text_answers),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )

    window.add_sticky_note_action.setChecked(True)
    assert session.canvas._sticky_note_enabled
    assert not window.select_text_action.isChecked()
    assert not window.select_annotation_action.isChecked()

    session.canvas.sticky_note_requested.emit(0, 0.35, 0.4)
    app.processEvents()

    annotations = window.annotation_service.list_annotations(session.document)
    assert len(annotations) == 1
    assert annotations[0].kind == AnnotationService.STICKY_NOTE
    assert annotations[0].content == "First note"
    assert session.annotation_selection is not None
    assert window.edit_sticky_note_action.isEnabled()

    window.edit_sticky_note_action.trigger()
    annotations = window.annotation_service.list_annotations(session.document)
    assert len(annotations) == 1
    assert annotations[0].content == "Updated note"

    center_x = (annotations[0].rects[0][0] + annotations[0].rects[0][2]) / 2
    center_y = (annotations[0].rects[0][1] + annotations[0].rects[0][3]) / 2
    window.select_annotation_action.setChecked(True)
    session.canvas.annotation_selection_requested.emit(0, center_x, center_y)
    app.processEvents()
    assert session.annotation_selection is not None
    assert session.annotation_selection.kind == AnnotationService.STICKY_NOTE

    window.delete_annotation_action.trigger()
    assert window.annotation_service.list_annotations(session.document) == []
    assert window.undo_action.text() == "Undo Delete Text"

    window.undo_action.trigger()
    restored = window.annotation_service.list_annotations(session.document)
    assert len(restored) == 1
    assert restored[0].content == "Updated note"

    assert window._save_session(session)
    reopened = fitz.open(pdf_path)
    try:
        reopened_annotations = AnnotationService().list_annotations(reopened)
        assert len(reopened_annotations) == 1
        assert reopened_annotations[0].kind == AnnotationService.STICKY_NOTE
        assert reopened_annotations[0].content == "Updated note"
    finally:
        reopened.close()