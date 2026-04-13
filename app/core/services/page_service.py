from __future__ import annotations

from pathlib import Path


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
