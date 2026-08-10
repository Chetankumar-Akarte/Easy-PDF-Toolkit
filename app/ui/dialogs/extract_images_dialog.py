from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)


@dataclass(frozen=True)
class ExtractImagesOptions:
    base_name: str
    page_label: str
    image_label: str
    target_format: str | None  # None = keep original


class ExtractImagesDialog(QDialog):
    """Single dialog collecting all image-extraction naming options."""

    _FORMATS = ["Keep original format", "PNG", "WEBP"]

    def __init__(self, default_base_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Extract Images")
        self.setMinimumWidth(500)

        self._base_edit = QLineEdit(default_base_name)
        self._base_edit.setMinimumHeight(30)

        self._page_edit = QLineEdit("page")
        self._page_edit.setMinimumHeight(30)

        self._image_edit = QLineEdit("image")
        self._image_edit.setMinimumHeight(30)

        self._format_combo = QComboBox()
        self._format_combo.addItems(self._FORMATS)
        self._format_combo.setMinimumHeight(30)

        self._preview_label = QLabel()
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._preview_label.setWordWrap(True)
        self._preview_label.setStyleSheet("color: gray; font-size: 11px;")

        # Borderless grid keeps labels and inputs column-aligned without QFormLayout quirks
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        rows = [
            ("Base name:", self._base_edit),
            ("Page label:", self._page_edit),
            ("Image label:", self._image_edit),
            ("Output format:", self._format_combo),
        ]
        for row_index, (label_text, widget) in enumerate(rows):
            lbl = QLabel(label_text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(lbl, row_index, 0)
            grid.addWidget(widget, row_index, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addLayout(grid)
        layout.addWidget(QLabel("Preview:"))
        layout.addWidget(self._preview_label)
        layout.addWidget(buttons)

        self._base_edit.textChanged.connect(self._update_preview)
        self._page_edit.textChanged.connect(self._update_preview)
        self._image_edit.textChanged.connect(self._update_preview)
        self._format_combo.currentIndexChanged.connect(self._update_preview)
        self._update_preview()

    # ------------------------------------------------------------------
    def _update_preview(self) -> None:
        base = self._base_edit.text().strip() or "<base_name>"
        pg = self._page_edit.text().strip() or "page"
        img = self._image_edit.text().strip() or "image"
        fmt_index = self._format_combo.currentIndex()
        ext = self._FORMATS[fmt_index].lower() if fmt_index > 0 else "<ext>"
        lines = [
            f"{base}_{pg}_1_{img}_1.{ext}",
            f"{base}_{pg}_1_{img}_2.{ext}",
            f"{base}_{pg}_2_{img}_1.{ext}",
        ]
        self._preview_label.setText("\n".join(lines))

    # ------------------------------------------------------------------
    def result_options(self) -> ExtractImagesOptions:
        base = self._base_edit.text().strip()
        page_label = self._page_edit.text().strip() or "page"
        image_label = self._image_edit.text().strip() or "image"
        fmt_index = self._format_combo.currentIndex()
        target_format = None if fmt_index == 0 else self._FORMATS[fmt_index].lower()
        return ExtractImagesOptions(
            base_name=base,
            page_label=page_label,
            image_label=image_label,
            target_format=target_format,
        )
