from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage


class PyMuPDFAdapter:
    """Thin wrapper for PyMuPDF operations."""

    def open_document(self, path: str):
        import fitz

        return fitz.open(path)

    def close_document(self, document) -> None:
        document.close()

    def page_count(self, document) -> int:
        return document.page_count

    def file_page_count(self, path: str) -> int:
        document = self.open_document(path)
        try:
            return self.page_count(document)
        finally:
            self.close_document(document)

    def page_sizes(self, document) -> list[tuple[int, int]]:
        sizes: list[tuple[int, int]] = []
        for page_index in range(document.page_count):
            rect = document.load_page(page_index).rect
            sizes.append((max(int(rect.width), 1), max(int(rect.height), 1)))
        return sizes

    _NATIVE_FORMATS = {"png", "webp"}

    def extract_images(
        self,
        document,
        output_directory: str,
        source_stem: str,
        *,
        page_label: str = "page",
        image_label: str = "image",
        target_format: str | None = None,
    ) -> list[Path]:
        from io import BytesIO

        from PIL import Image as PilImage

        destination = Path(output_directory).expanduser().resolve()
        destination.mkdir(parents=True, exist_ok=True)

        extracted: list[Path] = []
        seen_xrefs: set[int] = set()
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            for image_info in page.get_images(full=True):
                xref = image_info[0]
                if xref in seen_xrefs:
                    continue

                image = document.extract_image(xref)
                raw_ext = image.get("ext", "bin").lower()
                needs_conversion = (
                    target_format is not None and raw_ext not in self._NATIVE_FORMATS
                )
                extension = target_format if needs_conversion else raw_ext
                output_stem = (
                    f"{source_stem}_{page_label}_{page_index + 1}"
                    f"_{image_label}_{len(extracted) + 1}"
                )
                output_path = destination / f"{output_stem}.{extension}"
                duplicate_index = 2
                while output_path.exists():
                    output_path = destination / f"{output_stem}_{duplicate_index}.{extension}"
                    duplicate_index += 1
                if needs_conversion:
                    pil_img = PilImage.open(BytesIO(image["image"])).convert("RGBA")
                    pil_img.save(output_path, format=extension.upper())
                else:
                    output_path.write_bytes(image["image"])
                extracted.append(output_path)
                seen_xrefs.add(xref)

        return extracted

    def image_at_point(
        self,
        document,
        page_index: int,
        x_ratio: float,
        y_ratio: float,
    ) -> tuple[int, str] | None:
        import fitz

        page = document.load_page(page_index)
        page_rect = page.rect
        visual_point = fitz.Point(
            page_rect.x0 + max(0.0, min(x_ratio, 1.0)) * page_rect.width,
            page_rect.y0 + max(0.0, min(y_ratio, 1.0)) * page_rect.height,
        )
        point = visual_point * page.derotation_matrix

        matches = []
        for image_info in page.get_image_info(xrefs=True):
            xref = image_info.get("xref", 0)
            image_rect = fitz.Rect(image_info["bbox"])
            if xref > 0 and image_rect.contains(point):
                matches.append((image_rect.get_area(), xref))

        if not matches:
            return None

        _, xref = min(matches)
        image = document.extract_image(xref)
        return xref, image.get("ext", "bin")

    def extract_image(self, document, xref: int, output_path: str) -> Path:
        destination = Path(output_path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(document.extract_image(xref)["image"])
        return destination

    def render_page(
        self,
        document,
        page_index: int,
        zoom: float = 1.0,
        rotation_degrees: int = 0,
        invert_colors: bool = False,
        dpr: float = 1.0,
    ) -> QImage:
        import fitz

        page = document.load_page(page_index)
        matrix = fitz.Matrix(zoom * dpr, zoom * dpr).prerotate(rotation_degrees)
        pix = page.get_pixmap(matrix=matrix, alpha=False, annots=True)
        if invert_colors:
            pix.invert_irect()
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
        copied = image.copy()
        copied.setDevicePixelRatio(dpr)
        return copied
