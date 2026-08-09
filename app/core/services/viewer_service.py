from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchMatch:
    page_index: int
    rect: tuple[float, float, float, float]


@dataclass(frozen=True)
class TextSelection:
    page_index: int
    text: str
    rects: tuple[tuple[float, float, float, float], ...]


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

    def select_text(
        self,
        document,
        page_index: int,
        visual_rect: tuple[float, float, float, float],
    ) -> TextSelection | None:
        import fitz

        page = document.load_page(page_index)
        page_rect = page.rect
        left, top, right, bottom = visual_rect
        normalized = (
            min(left, right),
            min(top, bottom),
            max(left, right),
            max(top, bottom),
        )
        selection_rect = fitz.Rect(
            normalized[0] * page_rect.width,
            normalized[1] * page_rect.height,
            normalized[2] * page_rect.width,
            normalized[3] * page_rect.height,
        )

        selected_words: list[tuple] = []
        selected_rects: list[tuple[float, float, float, float]] = []
        for word in page.get_text("words", sort=True):
            source_rect = fitz.Rect(word[:4])
            word_rect = source_rect * page.rotation_matrix
            if not word_rect.intersects(selection_rect):
                continue
            selected_words.append(word)
            selected_rects.append(
                (
                    word_rect.x0 / page_rect.width,
                    word_rect.y0 / page_rect.height,
                    word_rect.x1 / page_rect.width,
                    word_rect.y1 / page_rect.height,
                )
            )

        if not selected_words:
            return None

        lines: list[list[str]] = []
        previous_line: tuple[int, int] | None = None
        for word in selected_words:
            line_key = (int(word[5]), int(word[6]))
            if line_key != previous_line:
                lines.append([])
                previous_line = line_key
            lines[-1].append(str(word[4]))
        text = "\n".join(" ".join(line) for line in lines)
        return TextSelection(page_index, text, tuple(selected_rects))
