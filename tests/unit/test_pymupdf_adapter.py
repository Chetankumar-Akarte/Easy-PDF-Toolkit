from __future__ import annotations

import fitz

from app.infra.pdf_engines.pymupdf_adapter import PyMuPDFAdapter


def test_extract_images_preserves_format_and_deduplicates_reused_images(tmp_path) -> None:
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 2), False)
    pixmap.clear_with(0x2F80ED)
    png_bytes = pixmap.tobytes("png")

    document = fitz.open()
    try:
        first_page = document.new_page()
        first_page.insert_image(fitz.Rect(0, 0, 20, 20), stream=png_bytes)
        second_page = document.new_page()
        second_page.insert_image(fitz.Rect(0, 0, 20, 20), stream=png_bytes)

        paths = PyMuPDFAdapter().extract_images(document, str(tmp_path), "sample")

        assert [path.name for path in paths] == ["sample_page_1_image_1.png"]
        assert paths[0].read_bytes().startswith(b"\x89PNG")

        repeated_paths = PyMuPDFAdapter().extract_images(document, str(tmp_path), "sample")
        assert [path.name for path in repeated_paths] == ["sample_page_1_image_1_2.png"]
    finally:
        document.close()


def test_image_at_point_finds_only_the_clicked_embedded_image(tmp_path) -> None:
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 2), False)
    pixmap.clear_with(0x2F80ED)
    document = fitz.open()
    try:
        page = document.new_page(width=100, height=100)
        xref = page.insert_image(fitz.Rect(20, 30, 70, 80), stream=pixmap.tobytes("png"))
        adapter = PyMuPDFAdapter()

        assert adapter.image_at_point(document, 0, 0.4, 0.5) == (xref, "png")
        assert adapter.image_at_point(document, 0, 0.1, 0.1) is None

        page.set_rotation(90)
        image_center = fitz.Point(45, 55) * page.rotation_matrix
        assert adapter.image_at_point(
            document,
            0,
            image_center.x / page.rect.width,
            image_center.y / page.rect.height,
        ) == (xref, "png")

        output_path = adapter.extract_image(document, xref, str(tmp_path / "selected.png"))
        assert output_path.read_bytes().startswith(b"\x89PNG")
    finally:
        document.close()