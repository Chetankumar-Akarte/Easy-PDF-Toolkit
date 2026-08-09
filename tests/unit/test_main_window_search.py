from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
from PySide6.QtWidgets import QApplication

from app.infra.storage.recent_files_repo import RecentFilesRepository
from app.infra.storage.settings_repo import SettingsRepository
from app.ui.main_window import MainWindow


def test_search_workflow_scans_navigates_and_clears(tmp_path: Path) -> None:
    pdf_path = tmp_path / "searchable.pdf"
    document = fitz.open()
    try:
        document.new_page().insert_text((40, 50), "needle one needle")
        document.new_page().insert_text((40, 50), "needle two")
        document.save(pdf_path)
    finally:
        document.close()

    app = QApplication.instance() or QApplication([])
    window = MainWindow(SettingsRepository(tmp_path), RecentFilesRepository(tmp_path))
    window._open_document_by_path(str(pdf_path))
    window._show_search_bar()
    window.search_input.setText("needle")
    window._perform_search()
    while window._search_scan_session is not None:
        window._process_search_page()

    session = window._current_session()
    assert session is not None
    assert len(session.search_matches) == 3
    assert window.search_result_label.text() == "1 / 3"

    window._go_next_search_match()
    assert window.search_result_label.text() == "2 / 3"
    window._go_previous_search_match()
    assert window.search_result_label.text() == "1 / 3"

    window.search_input.setText("missing")
    assert session.search_matches == []
    window._perform_search()
    while window._search_scan_session is not None:
        window._process_search_page()

    assert window.search_result_label.text() == "0 / 0"
    assert window.search_input.property("noResults") is True

    window._hide_search_bar()
    assert window.search_bar.isHidden()
    assert session.search_matches == []
    app.processEvents()