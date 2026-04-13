"""Unit tests for PageService page-range parsing and split filename templating."""
from __future__ import annotations

import pytest

from app.core.services.page_service import PageService


@pytest.fixture()
def svc() -> PageService:
    return PageService()


# ──────────────────────────────────────────────────────────────────────────────
# parse_page_ranges — valid inputs
# ──────────────────────────────────────────────────────────────────────────────

class TestParsePageRangesValid:
    def test_single_page(self, svc: PageService) -> None:
        assert svc.parse_page_ranges("3", 10) == [2]

    def test_single_page_first(self, svc: PageService) -> None:
        assert svc.parse_page_ranges("1", 10) == [0]

    def test_single_page_last(self, svc: PageService) -> None:
        assert svc.parse_page_ranges("10", 10) == [9]

    def test_comma_list(self, svc: PageService) -> None:
        assert svc.parse_page_ranges("1,3,5", 10) == [0, 2, 4]

    def test_range(self, svc: PageService) -> None:
        assert svc.parse_page_ranges("5-7", 10) == [4, 5, 6]

    def test_mixed_commas_and_range(self, svc: PageService) -> None:
        assert svc.parse_page_ranges("1,3,5-7", 10) == [0, 2, 4, 5, 6]

    def test_leading_trailing_spaces_ignored(self, svc: PageService) -> None:
        assert svc.parse_page_ranges("  1 , 3 ", 10) == [0, 2]

    def test_deduplication_comma(self, svc: PageService) -> None:
        result = svc.parse_page_ranges("2,2,2", 10)
        assert result == [1]

    def test_deduplication_range_overlap(self, svc: PageService) -> None:
        result = svc.parse_page_ranges("1-3,2-4", 10)
        assert result == [0, 1, 2, 3]

    def test_single_page_range(self, svc: PageService) -> None:
        # "5-5" is a range of length 1, should work
        assert svc.parse_page_ranges("5-5", 10) == [4]

    def test_full_document(self, svc: PageService) -> None:
        assert svc.parse_page_ranges("1-5", 5) == [0, 1, 2, 3, 4]


# ──────────────────────────────────────────────────────────────────────────────
# parse_page_ranges — validation / error cases
# ──────────────────────────────────────────────────────────────────────────────

class TestParsePageRangesErrors:
    def test_empty_string_raises(self, svc: PageService) -> None:
        with pytest.raises(ValueError, match="empty"):
            svc.parse_page_ranges("", 10)

    def test_whitespace_only_raises(self, svc: PageService) -> None:
        with pytest.raises(ValueError, match="empty"):
            svc.parse_page_ranges("   ", 10)

    def test_page_out_of_bounds(self, svc: PageService) -> None:
        with pytest.raises(ValueError, match="outside"):
            svc.parse_page_ranges("11", 10)

    def test_range_end_out_of_bounds(self, svc: PageService) -> None:
        with pytest.raises(ValueError, match="outside"):
            svc.parse_page_ranges("8-12", 10)

    def test_reversed_range_raises(self, svc: PageService) -> None:
        with pytest.raises(ValueError, match="Invalid range order"):
            svc.parse_page_ranges("7-3", 10)

    def test_non_numeric_token_raises(self, svc: PageService) -> None:
        with pytest.raises(ValueError):
            svc.parse_page_ranges("a", 10)

    def test_non_numeric_in_range_raises(self, svc: PageService) -> None:
        with pytest.raises(ValueError):
            svc.parse_page_ranges("1-b", 10)

    def test_zero_page_raises(self, svc: PageService) -> None:
        with pytest.raises(ValueError):
            svc.parse_page_ranges("0", 10)


# ──────────────────────────────────────────────────────────────────────────────
# build_split_filename — valid inputs / template expansion
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildSplitFilename:
    def test_default_template_produces_named_file(self, svc: PageService) -> None:
        result = svc.build_split_filename(
            source_stem="report",
            split_size=10,
            part_index=1,
            start_page=1,
            end_page=10,
            template="{filename}_split_{range}.pdf",
        )
        # no {index} in template → _part_1 appended automatically
        assert result == "report_split_10_part_1.pdf"

    def test_filename_placeholder(self, svc: PageService) -> None:
        result = svc.build_split_filename(
            source_stem="mydoc",
            split_size=5,
            part_index=2,
            start_page=6,
            end_page=10,
            template="{filename}_chunk.pdf",
        )
        # no {index} in template → _part_2 appended
        assert result == "mydoc_chunk_part_2.pdf"

    def test_index_placeholder_prevents_auto_suffix(self, svc: PageService) -> None:
        result = svc.build_split_filename(
            source_stem="book",
            split_size=10,
            part_index=3,
            start_page=21,
            end_page=30,
            template="{filename}_{index}.pdf",
        )
        assert result == "book_3.pdf"

    def test_start_end_placeholders(self, svc: PageService) -> None:
        result = svc.build_split_filename(
            source_stem="doc",
            split_size=10,
            part_index=1,
            start_page=1,
            end_page=10,
            template="{filename}_pages_{start}-{end}.pdf",
        )
        # no {index} → _part_1 appended
        assert result == "doc_pages_1-10_part_1.pdf"

    def test_all_placeholders(self, svc: PageService) -> None:
        result = svc.build_split_filename(
            source_stem="test",
            split_size=10,
            part_index=2,
            start_page=11,
            end_page=20,
            template="{filename}_{index}_{start}-{end}_s{range}.pdf",
        )
        assert result == "test_2_11-20_s10.pdf"

    def test_missing_suffix_defaults_to_pdf(self, svc: PageService) -> None:
        result = svc.build_split_filename(
            source_stem="scan",
            split_size=5,
            part_index=1,
            start_page=1,
            end_page=5,
            template="{filename}_{index}",
        )
        # no extension in template → .pdf added
        assert result.endswith(".pdf")

    def test_empty_template_uses_default(self, svc: PageService) -> None:
        result = svc.build_split_filename(
            source_stem="notes",
            split_size=10,
            part_index=1,
            start_page=1,
            end_page=10,
            template="",
        )
        # fallback template "{filename}_split_{range}.pdf" → no {index} → _part_1 appended
        assert result == "notes_split_10_part_1.pdf"

    def test_second_part_has_correct_index(self, svc: PageService) -> None:
        r1 = svc.build_split_filename("doc", 10, 1, 1, 10, "{filename}_{index}.pdf")
        r2 = svc.build_split_filename("doc", 10, 2, 11, 20, "{filename}_{index}.pdf")
        assert r1 == "doc_1.pdf"
        assert r2 == "doc_2.pdf"

    def test_52_page_split_last_chunk_naming(self, svc: PageService) -> None:
        """Mirrors the real-world 52-page / 10 split producing a 6th part with 2 pages."""
        result = svc.build_split_filename(
            source_stem="report",
            split_size=10,
            part_index=6,
            start_page=51,
            end_page=52,
            template="{filename}_part_{index}.pdf",
        )
        assert result == "report_part_6.pdf"
