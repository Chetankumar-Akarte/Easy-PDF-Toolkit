from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchMatch:
    page_index: int
    rect: tuple[float, float, float, float]


class ViewerService:
    """Document-level viewer operations that are independent of Qt widgets."""

    def search_text(self, document, query: str) -> list[SearchMatch]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        matches: list[SearchMatch] = []
        for page_index in range(document.page_count):
            matches.extend(self.search_page(document, page_index, normalized_query))

        return matches

    def search_page(self, document, page_index: int, query: str) -> list[SearchMatch]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        page = document.load_page(page_index)
        visual_page_rect = page.rect
        matches: list[SearchMatch] = []
        for match_rect in page.search_for(normalized_query):
            visual_rect = match_rect * page.rotation_matrix
            matches.append(
                SearchMatch(
                    page_index=page_index,
                    rect=(
                        visual_rect.x0 / visual_page_rect.width,
                        visual_rect.y0 / visual_page_rect.height,
                        visual_rect.x1 / visual_page_rect.width,
                        visual_rect.y1 / visual_page_rect.height,
                    ),
                )
            )
        return matches
