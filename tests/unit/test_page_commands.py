from __future__ import annotations

import fitz

from app.core.commands import (
    CommandHistory,
    DeletePageCommand,
    InsertBlankPagesCommand,
    ReorderPagesCommand,
    RotatePageCommand,
)
from app.core.services.page_service import PageService


def _document_with_labels(count: int = 3):
    document = fitz.open()
    for page_number in range(1, count + 1):
        document.new_page(width=300 + page_number, height=400 + page_number).insert_text(
            (20, 30),
            f"page-{page_number}",
        )
    return document


def _labels(document) -> list[str]:
    return [document[index].get_text().strip() for index in range(document.page_count)]


def test_command_history_tracks_clean_checkpoint_and_redo_branch() -> None:
    document = _document_with_labels(1)
    try:
        history = CommandHistory()
        service = PageService()
        history.execute(RotatePageCommand(service, document, 0, 90))
        assert history.can_undo and history.is_dirty
        history.mark_clean()
        assert not history.is_dirty

        history.undo()
        assert document[0].rotation == 0
        assert history.is_dirty and history.can_redo
        history.redo()
        assert document[0].rotation == 90
        assert not history.is_dirty

        history.undo()
        history.execute(RotatePageCommand(service, document, 0, -90))
        assert not history.can_redo
        assert history.is_dirty
    finally:
        document.close()


def test_insert_delete_and_reorder_commands_round_trip() -> None:
    document = _document_with_labels()
    try:
        history = CommandHistory()
        service = PageService()

        history.execute(InsertBlankPagesCommand(service, document, 1, 612, 792, 2))
        assert document.page_count == 5
        history.undo()
        assert _labels(document) == ["page-1", "page-2", "page-3"]
        history.redo()
        assert document.page_count == 5

        history.execute(DeletePageCommand(service, document, 0))
        assert "page-1" not in _labels(document)
        history.undo()
        assert _labels(document)[0] == "page-1"
        history.redo()
        assert "page-1" not in _labels(document)

        order = list(reversed(range(document.page_count)))
        before_reorder = _labels(document)
        history.execute(ReorderPagesCommand(service, document, order))
        assert _labels(document) == list(reversed(before_reorder))
        history.undo()
        assert _labels(document) == before_reorder
        history.redo()
        assert _labels(document) == list(reversed(before_reorder))
    finally:
        document.close()