from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class MergeSource:
    path: str
    page_indices: tuple[int, ...]


class MergeCancelledError(RuntimeError):
    """Raised when a PDF merge is cancelled before completion."""


class PageService:
    """PDF page mutation operations — rotate, delete, reorder."""

    def rotate_page(self, document, page_index: int, degrees: int) -> None:
        """Rotate a single page by the given degrees (cumulative, snaps to 0/90/180/270)."""
        page = document[page_index]
        new_rotation = (page.rotation + degrees) % 360
        page.set_rotation(new_rotation)

    def delete_page(self, document, page_index: int) -> None:
        """Delete the page at the given index."""
        document.delete_page(page_index)

    def reorder_pages(self, document, new_order: list[int]) -> None:
        """Reorder document pages using a list of current-state page indices in desired order."""
        document.select(new_order)

    def insert_blank_pages(
        self,
        document,
        insertion_index: int,
        width: float,
        height: float,
        count: int = 1,
    ) -> list[int]:
        """Insert blank pages before ``insertion_index`` and return their final indices."""
        if insertion_index < 0 or insertion_index > document.page_count:
            raise ValueError("Insertion position is outside this document.")
        if width <= 0 or height <= 0:
            raise ValueError("Page dimensions must be greater than zero.")
        if count <= 0:
            raise ValueError("Page count must be greater than zero.")

        inserted_indices: list[int] = []
        for offset in range(count):
            page_index = insertion_index + offset
            document.new_page(pno=page_index, width=width, height=height)
            inserted_indices.append(page_index)
        return inserted_indices

    def merge_pdfs(
        self,
        sources: list[MergeSource],
        output_path: str,
        progress: Callable[[int, int, str], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> str:
        """Merge ordered source page selections into an atomically written PDF."""
        import fitz

        if not sources:
            raise ValueError("Select at least one PDF to merge.")

        destination = Path(output_path).expanduser().resolve()
        if destination.suffix.lower() != ".pdf":
            destination = destination.with_suffix(".pdf")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.merging")

        merged = fitz.open()
        merged_toc: list[list] = []
        first_metadata: dict | None = None
        output_page_count = 0
        try:
            for source_number, source_spec in enumerate(sources, start=1):
                if is_cancelled is not None and is_cancelled():
                    raise MergeCancelledError("PDF merge cancelled.")

                source_path = Path(source_spec.path).expanduser().resolve()
                if not source_path.is_file():
                    raise FileNotFoundError(f"PDF not found: {source_path}")

                source = fitz.open(str(source_path))
                try:
                    page_indices = list(source_spec.page_indices)
                    if not page_indices:
                        raise ValueError(f"No pages selected from {source_path.name}.")
                    if len(set(page_indices)) != len(page_indices):
                        raise ValueError(f"Duplicate pages selected from {source_path.name}.")
                    if any(index < 0 or index >= source.page_count for index in page_indices):
                        raise ValueError(f"Page selection is outside {source_path.name}.")

                    if first_metadata is None:
                        first_metadata = dict(source.metadata)

                    source_to_output: dict[int, int] = {}
                    for page_index in page_indices:
                        if is_cancelled is not None and is_cancelled():
                            raise MergeCancelledError("PDF merge cancelled.")
                        merged.insert_pdf(source, from_page=page_index, to_page=page_index)
                        output_page_count += 1
                        source_to_output[page_index + 1] = output_page_count

                    previous_level = 0
                    for item in source.get_toc(simple=True):
                        level, title, source_page = item[:3]
                        output_page = source_to_output.get(source_page)
                        if output_page is None:
                            continue
                        normalized_level = 1 if previous_level == 0 else min(level, previous_level + 1)
                        merged_toc.append([normalized_level, title, output_page])
                        previous_level = normalized_level
                finally:
                    source.close()

                if progress is not None:
                    progress(source_number, len(sources), source_path.name)

            if merged.page_count == 0:
                raise ValueError("The selected sources contain no pages.")
            if first_metadata:
                merged.set_metadata(first_metadata)
            if merged_toc:
                merged.set_toc(merged_toc)

            if temporary.exists():
                temporary.unlink()
            merged.save(str(temporary), garbage=3, deflate=True)
            if is_cancelled is not None and is_cancelled():
                raise MergeCancelledError("PDF merge cancelled.")
            temporary.replace(destination)
            return str(destination)
        finally:
            merged.close()
            if temporary.exists():
                temporary.unlink()

    def parse_page_ranges(self, page_range_text: str, page_count: int) -> list[int]:
        """Parse 1-based ranges like `1,3,5-7` into 0-based unique page indices."""
        cleaned = (page_range_text or "").replace(" ", "")
        if not cleaned:
            raise ValueError("Page range cannot be empty.")

        pages: list[int] = []
        seen: set[int] = set()

        for token in cleaned.split(","):
            if not token:
                continue

            if "-" in token:
                parts = token.split("-", 1)
                if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
                    raise ValueError(f"Invalid range token: {token}")
                start = int(parts[0])
                end = int(parts[1])
                if start <= 0 or end <= 0:
                    raise ValueError("Page numbers must be positive.")
                if start > end:
                    raise ValueError(f"Invalid range order: {token}")
                for one_based in range(start, end + 1):
                    if one_based > page_count:
                        raise ValueError(f"Page {one_based} is outside this document (max: {page_count}).")
                    index = one_based - 1
                    if index not in seen:
                        seen.add(index)
                        pages.append(index)
                continue

            if not token.isdigit():
                raise ValueError(f"Invalid page token: {token}")
            one_based = int(token)
            if one_based <= 0:
                raise ValueError("Page numbers must be positive.")
            if one_based > page_count:
                raise ValueError(f"Page {one_based} is outside this document (max: {page_count}).")
            index = one_based - 1
            if index not in seen:
                seen.add(index)
                pages.append(index)

        if not pages:
            raise ValueError("No pages selected.")

        return pages

    def extract_pages(self, document, page_indices: list[int], output_path: str) -> str:
        """Create a new PDF with selected pages from the source document."""
        import fitz

        destination = Path(output_path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)

        result = fitz.open()
        try:
            for page_index in page_indices:
                result.insert_pdf(document, from_page=page_index, to_page=page_index)
            result.save(str(destination), garbage=3, deflate=True)
        finally:
            result.close()

        return str(destination)

    def build_split_filename(
        self,
        source_stem: str,
        split_size: int,
        part_index: int,
        start_page: int,
        end_page: int,
        template: str,
    ) -> str:
        """Render a split output filename from a template string.

        Supported placeholders: {filename}, {range}, {index}, {start}, {end}.
        If {index} is absent the part number is appended automatically.
        The .pdf extension is added when the template has no extension.
        """
        template_text = (template or "").strip() or "{filename}_split_{range}.pdf"
        rendered = (
            template_text
            .replace("{filename}", source_stem)
            .replace("{range}", str(split_size))
            .replace("{index}", str(part_index))
            .replace("{start}", str(start_page))
            .replace("{end}", str(end_page))
        )

        candidate = Path(rendered)
        stem = candidate.stem or f"{source_stem}_split_{split_size}"
        suffix = candidate.suffix if candidate.suffix else ".pdf"

        if "{index}" not in template_text:
            stem = f"{stem}_part_{part_index}"

        return f"{stem}{suffix}"
