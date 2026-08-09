from __future__ import annotations

import fitz

from app.core.services.viewer_service import ViewerService


def test_search_text_returns_ordered_normalized_matches() -> None:
    document = fitz.open()
    try:
        first_page = document.new_page(width=200, height=100)
        first_page.insert_text((20, 30), "Alpha beta alpha")
        second_page = document.new_page(width=100, height=200)
        second_page.insert_text((20, 40), "ALPHA")
        second_page.set_rotation(90)

        matches = ViewerService().search_text(document, "alpha")

        assert [match.page_index for match in matches] == [0, 0, 1]
        assert all(0.0 <= coordinate <= 1.0 for match in matches for coordinate in match.rect)
        assert matches[0].rect[0] < matches[1].rect[0]
    finally:
        document.close()


def test_search_text_ignores_blank_queries() -> None:
    document = fitz.open()
    try:
        document.new_page().insert_text((20, 30), "searchable")
        assert ViewerService().search_text(document, "   ") == []
    finally:
        document.close()