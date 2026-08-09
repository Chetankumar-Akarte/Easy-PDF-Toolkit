from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnnotationInfo:
    page_index: int
    xref: int
    kind: str
    content: str
    color: tuple[float, float, float]
    opacity: float


class AnnotationService:
    """Creates and manages native PDF annotations."""

    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKEOUT = "strikeout"
    MARKUP_KINDS = (HIGHLIGHT, UNDERLINE, STRIKEOUT)

    def add_markup(
        self,
        document,
        page_index: int,
        kind: str,
        visual_rects: tuple[tuple[float, float, float, float], ...],
        selected_text: str,
        color: tuple[float, float, float],
        opacity: float = 0.45,
        author: str = "Easy PDF Tool Kit",
    ) -> int:
        import fitz

        if kind not in self.MARKUP_KINDS:
            raise ValueError(f"Unsupported markup type: {kind}")
        if not visual_rects:
            raise ValueError("Select text before adding markup.")

        page = document.load_page(page_index)
        visual_page = page.rect
        quads = []
        for rect in visual_rects:
            visual_rect = fitz.Rect(
                rect[0] * visual_page.width,
                rect[1] * visual_page.height,
                rect[2] * visual_page.width,
                rect[3] * visual_page.height,
            )
            source_rect = visual_rect * page.derotation_matrix
            quads.append(source_rect)

        if kind == self.HIGHLIGHT:
            annotation = page.add_highlight_annot(quads)
        elif kind == self.UNDERLINE:
            annotation = page.add_underline_annot(quads)
        else:
            annotation = page.add_strikeout_annot(quads)
        annotation.set_colors(stroke=color)
        annotation.set_opacity(max(0.0, min(float(opacity), 1.0)))
        annotation.set_info(title=author, content=selected_text)
        annotation.update()
        return annotation.xref

    def delete_annotation(self, document, page_index: int, xref: int) -> None:
        page = document.load_page(page_index)
        annotation = page.first_annot
        while annotation is not None:
            if annotation.xref == xref:
                page.delete_annot(annotation)
                return
            annotation = annotation.next
        raise ValueError("Annotation no longer exists.")

    def list_annotations(self, document, page_index: int | None = None) -> list[AnnotationInfo]:
        page_indices = range(document.page_count) if page_index is None else [page_index]
        annotations: list[AnnotationInfo] = []
        for index in page_indices:
            page = document.load_page(index)
            annotation = page.first_annot
            while annotation is not None:
                annotation_type = str(annotation.type[1]).lower().replace(" ", "")
                if annotation_type in self.MARKUP_KINDS:
                    stroke = annotation.colors.get("stroke") or (1.0, 1.0, 0.0)
                    annotations.append(
                        AnnotationInfo(
                            page_index=index,
                            xref=annotation.xref,
                            kind=annotation_type,
                            content=annotation.info.get("content", ""),
                            color=tuple(stroke[:3]),
                            opacity=float(annotation.opacity),
                        )
                    )
                annotation = annotation.next
        return annotations
