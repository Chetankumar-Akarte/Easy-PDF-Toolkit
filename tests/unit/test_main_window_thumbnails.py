from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication

from app.infra.storage.recent_files_repo import RecentFilesRepository
from app.infra.storage.settings_repo import SettingsRepository
from app.ui.main_window import MainWindow


def test_pending_thumbnail_animates_and_prioritizes_clicked_page(tmp_path: Path) -> None:
    pdf_path = tmp_path / "thumbnail-progress.pdf"
    document = fitz.open()
    try:
        for page_index in range(8):
            document.new_page().insert_text((40, 50), f"Page {page_index + 1}")
        document.save(pdf_path)
    finally:
        document.close()

    app = QApplication.instance() or QApplication([])
    window = MainWindow(SettingsRepository(tmp_path), RecentFilesRepository(tmp_path))
    window.THUMBNAIL_CACHE_LIMIT = 3
    window._open_document_by_path(str(pdf_path))
    session = window._current_session()
    assert session is not None
    assert window.search_button.defaultAction() is window.search_action
    assert window._thumbnail_progress_timer.isActive()
    assert all(
        not window.thumbnail_list.item(page_index).icon().isNull()
        for page_index in range(session.page_count)
    )

    before = window.thumbnail_list.item(0).icon().pixmap(110, 150).toImage()
    window._animate_thumbnail_progress()
    after = window.thumbnail_list.item(0).icon().pixmap(110, 150).toImage()
    assert before != after

    target_page = 7
    assert target_page not in session.thumbnail_cache
    window.thumbnail_list.setCurrentRow(target_page)
    assert session.current_page == target_page
    assert session.render_queue[0] == target_page

    window._process_background_render_step()
    assert target_page in session.thumbnail_cache

    guard = 0
    while (session.render_queue or session.thumbnail_queue) and guard < 100:
        window._process_background_render_step()
        guard += 1

    assert target_page in session.page_cache
    assert len(session.thumbnail_cache) <= window.THUMBNAIL_CACHE_LIMIT
    assert all(
        window.thumbnail_list.item(page_index).data(window.THUMBNAIL_LOADING_ROLE) is False
        for page_index in range(session.page_count)
    )
    assert not window._thumbnail_progress_timer.isActive()
    app.processEvents()