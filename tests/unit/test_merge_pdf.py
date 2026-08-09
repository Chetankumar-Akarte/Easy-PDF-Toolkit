from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pytest
from PySide6.QtWidgets import QApplication, QDialog

import app.ui.main_window as main_window_module
from app.infra.storage.recent_files_repo import RecentFilesRepository
from app.infra.storage.settings_repo import SettingsRepository
from app.ui.dialogs import MergeDialogSource, MergePdfDialog, MergePdfRequest
from app.ui.main_window import MainWindow
from app.ui.theme import get_theme


def _create_pdf(path: Path, labels: list[str]) -> None:
    document = fitz.open()
    try:
        for label in labels:
            document.new_page().insert_text((20, 30), label)
        document.save(path)
    finally:
        document.close()


def test_merge_dialog_manages_order_ranges_and_output(tmp_path: Path) -> None:
    first_path = tmp_path / "first.pdf"
    second_path = tmp_path / "second.pdf"
    _create_pdf(first_path, ["first"])
    _create_pdf(second_path, ["second-1", "second-2"])

    app = QApplication.instance() or QApplication([])
    dialog = MergePdfDialog(
        page_count_loader=lambda path: fitz.open(path).page_count,
        theme=get_theme("light"),
        initial_paths=[str(first_path), str(second_path), str(first_path)],
    )

    assert dialog.source_table.rowCount() == 2
    assert dialog.merge_button.isEnabled()
    assert dialog.summary_label.text() == "2 PDFs · up to 3 pages"
    dialog.source_table.selectRow(1)
    dialog.move_up_button.click()
    dialog.source_table.item(0, 2).setText("2")
    dialog.output_input.setText(str(tmp_path / "result.pdf"))

    request = dialog.build_request()
    assert [Path(source.path).name for source in request.sources] == ["second.pdf", "first.pdf"]
    assert request.sources[0].page_range_text == "2"
    assert request.output_path.endswith("result.pdf")
    assert request.open_result

    dialog.source_table.row_move_requested.emit(0, 1)
    assert [Path(source.path).name for source in dialog.sources()] == ["first.pdf", "second.pdf"]
    app.processEvents()


def test_merge_action_creates_and_opens_ordered_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_path = tmp_path / "first.pdf"
    second_path = tmp_path / "second.pdf"
    output_path = tmp_path / "merged.pdf"
    _create_pdf(first_path, ["first-1", "first-2"])
    _create_pdf(second_path, ["second-1", "second-2"])

    class AcceptedDialog:
        def __init__(self, **kwargs) -> None:
            assert kwargs["initial_paths"] == [str(first_path.resolve())]

        def exec(self):
            return QDialog.DialogCode.Accepted

        def build_request(self) -> MergePdfRequest:
            return MergePdfRequest(
                sources=(
                    MergeDialogSource(str(second_path), 2, "2"),
                    MergeDialogSource(str(first_path), 2, "All"),
                ),
                output_path=str(output_path),
                open_result=True,
            )

    QApplication.instance() or QApplication([])
    window = MainWindow(SettingsRepository(tmp_path), RecentFilesRepository(tmp_path))
    assert window.merge_pdfs_action.isEnabled()
    assert not window.merge_pdfs_action.icon().isNull()
    assert window.merge_pdfs_action.shortcut().toString() == "Ctrl+Shift+M"
    ribbon_layout = window.action_bar.layout()
    assert ribbon_layout.indexOf(window.merge_pdfs_button) + 1 == ribbon_layout.indexOf(
        window.extract_images_button
    )
    window._open_document_by_path(str(first_path))
    monkeypatch.setattr(main_window_module, "MergePdfDialog", AcceptedDialog)

    window.merge_pdfs_action.trigger()

    session = window._current_session()
    assert session is not None
    assert Path(session.path) == output_path.resolve()
    assert session.page_count == 3
    assert [session.document[index].get_text().strip() for index in range(3)] == [
        "second-2",
        "first-1",
        "first-2",
    ]