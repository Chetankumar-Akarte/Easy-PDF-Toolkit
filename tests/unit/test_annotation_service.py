from __future__ import annotations

import fitz
import pytest

from app.core.commands import AddMarkupAnnotationCommand, CommandHistory, DeleteAnnotationCommand
from app.core.services.annotation_service import AnnotationService
from app.core.services.viewer_service import ViewerService


@pytest.mark.parametrize("kind", AnnotationService.MARKUP_KINDS)
def test_native_markup_persists_and_round_trips_through_history(kind: str, tmp_path) -> None:
    path = tmp_path / f"{kind}.pdf"
    document = fitz.open()
    document.new_page(width=400, height=300).insert_text((50, 80), "Alpha Beta")
    document[0].set_rotation(90)
    document.save(path)
    document.close()

    document = fitz.open(path)
    try:
        viewer = ViewerService()
        service = AnnotationService()
        page = document[0]
        word = page.get_text("words", sort=True)[1]
        visual_word = fitz.Rect(word[:4]) * page.rotation_matrix
        selection = viewer.select_text(
            document,
            0,
            (
                visual_word.x0 / page.rect.width,
                visual_word.y0 / page.rect.height,
                visual_word.x1 / page.rect.width,
                visual_word.y1 / page.rect.height,
            ),
        )
        assert selection is not None

        history = CommandHistory()
        command = AddMarkupAnnotationCommand(
            service,
            document,
            0,
            kind,
            selection.rects,
            selection.text,
            (1.0, 0.8, 0.0),
        )
        history.execute(command)
        annotations = service.list_annotations(document)
        assert len(annotations) == 1
        assert annotations[0].kind == kind
        assert annotations[0].content == "Beta"
        center_x = (annotations[0].rects[0][0] + annotations[0].rects[0][2]) / 2
        center_y = (annotations[0].rects[0][1] + annotations[0].rects[0][3]) / 2
        assert service.annotation_at_point(document, 0, center_x, center_y) == annotations[0]

        history.undo()
        assert service.list_annotations(document) == []
        history.redo()
        assert len(service.list_annotations(document)) == 1

        document.saveIncr()
    finally:
        document.close()

    reopened = fitz.open(path)
    try:
        assert len(AnnotationService().list_annotations(reopened)) == 1
    finally:
        reopened.close()


def test_delete_annotation_command_round_trips_original_properties() -> None:
    document = fitz.open()
    try:
        page = document.new_page(width=400, height=300)
        page.insert_text((50, 80), "Delete this markup")
        service = AnnotationService()
        viewer = ViewerService()
        word = page.get_text("words", sort=True)[1]
        rect = fitz.Rect(word[:4])
        selection = viewer.select_text(
            document,
            0,
            (rect.x0 / page.rect.width, rect.y0 / page.rect.height, rect.x1 / page.rect.width, rect.y1 / page.rect.height),
        )
        assert selection is not None
        xref = service.add_markup(document, 0, service.UNDERLINE, selection.rects, selection.text, (0.2, 0.4, 0.8), 0.7)
        original = service.list_annotations(document)[0]
        assert original.xref == xref

        history = CommandHistory()
        history.execute(DeleteAnnotationCommand(service, document, original))
        assert service.list_annotations(document) == []
        history.undo()
        restored = service.list_annotations(document)[0]
        assert restored.kind == original.kind
        assert restored.content == original.content
        assert restored.color == pytest.approx(original.color)
        assert restored.opacity == pytest.approx(original.opacity)
        history.redo()
        assert service.list_annotations(document) == []
    finally:
        document.close()