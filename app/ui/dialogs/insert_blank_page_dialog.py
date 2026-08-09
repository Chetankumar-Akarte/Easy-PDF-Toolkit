from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeColors


@dataclass(frozen=True)
class InsertBlankPageRequest:
    insertion_index: int
    width: float
    height: float
    count: int


class InsertBlankPageDialog(QDialog):
    PAGE_SIZES = {
        "A4": (595.0, 842.0),
        "Letter": (612.0, 792.0),
        "Legal": (612.0, 1008.0),
    }

    def __init__(
        self,
        current_page: int,
        page_count: int,
        current_page_size: tuple[int, int],
        theme: ThemeColors,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._current_page = current_page
        self._page_count = page_count
        self._current_page_size = (float(current_page_size[0]), float(current_page_size[1]))
        self._theme = theme

        self.setWindowTitle("Insert Blank Pages")
        self.setModal(True)
        self.setMinimumWidth(500)
        self._build_ui()
        self._apply_style()
        self._update_preview()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        title = QLabel("Insert Blank Pages", self)
        title.setObjectName("dialogTitle")
        root.addWidget(title)

        subtitle = QLabel(
            f"Current page: {self._current_page + 1} of {self._page_count}",
            self,
        )
        subtitle.setObjectName("dialogSubtitle")
        root.addWidget(subtitle)

        card = QFrame(self)
        card.setObjectName("infoCard")
        form = QFormLayout(card)
        form.setContentsMargins(16, 14, 16, 14)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.position_combo = QComboBox(card)
        self.position_combo.addItem("Before current page", "before")
        self.position_combo.addItem("After current page", "after")
        self.position_combo.setCurrentIndex(1)
        form.addRow("Insert position", self.position_combo)

        self.size_combo = QComboBox(card)
        self.size_combo.addItem("Same as current page", "current")
        for page_size in self.PAGE_SIZES:
            self.size_combo.addItem(page_size, page_size)
        form.addRow("Page size", self.size_combo)

        self.orientation_combo = QComboBox(card)
        self.orientation_combo.addItem("Portrait", "portrait")
        self.orientation_combo.addItem("Landscape", "landscape")
        current_width, current_height = self._current_page_size
        self.orientation_combo.setCurrentIndex(1 if current_width > current_height else 0)
        form.addRow("Orientation", self.orientation_combo)

        self.count_spin = QSpinBox(card)
        self.count_spin.setRange(1, 100)
        self.count_spin.setValue(1)
        form.addRow("Quantity", self.count_spin)

        self.preview_label = QLabel(card)
        self.preview_label.setObjectName("dimensionPreview")
        form.addRow("Result", self.preview_label)
        root.addWidget(card)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        cancel_button = QPushButton("Cancel", self)
        cancel_button.setObjectName("dialogButtonSecondary")
        cancel_button.clicked.connect(self.reject)
        button_row.addWidget(cancel_button)
        self.insert_button = QPushButton("Insert", self)
        self.insert_button.setObjectName("dialogButtonPrimary")
        self.insert_button.setDefault(True)
        self.insert_button.clicked.connect(self.accept)
        button_row.addWidget(self.insert_button)
        root.addLayout(button_row)

        self.size_combo.currentIndexChanged.connect(self._update_preview)
        self.orientation_combo.currentIndexChanged.connect(self._update_preview)
        self.count_spin.valueChanged.connect(self._update_preview)
        self.position_combo.currentIndexChanged.connect(self._update_preview)

    def _resolved_size(self) -> tuple[float, float]:
        size_key = self.size_combo.currentData()
        width, height = (
            self._current_page_size
            if size_key == "current"
            else self.PAGE_SIZES[str(size_key)]
        )
        short_edge, long_edge = sorted((width, height))
        if self.orientation_combo.currentData() == "landscape":
            return long_edge, short_edge
        return short_edge, long_edge

    def _update_preview(self) -> None:
        width, height = self._resolved_size()
        count = self.count_spin.value()
        page_word = "page" if count == 1 else "pages"
        position = self.position_combo.currentData()
        self.preview_label.setText(
            f"{count} blank {page_word} · {width:.0f} × {height:.0f} pt "
            f"{position} Page {self._current_page + 1}"
        )

    def build_request(self) -> InsertBlankPageRequest:
        position = self.position_combo.currentData()
        insertion_index = self._current_page if position == "before" else self._current_page + 1
        width, height = self._resolved_size()
        return InsertBlankPageRequest(
            insertion_index=insertion_index,
            width=width,
            height=height,
            count=self.count_spin.value(),
        )

    def _apply_style(self) -> None:
        theme = self._theme
        self.setStyleSheet(f"QDialog {{ background: {theme.bg_panel}; color: {theme.text_primary}; }}")
        self.findChild(QLabel, "dialogTitle").setStyleSheet(
            f"font-size: 15pt; font-weight: 700; color: {theme.text_primary};"
        )
        self.findChild(QLabel, "dialogSubtitle").setStyleSheet(
            f"color: {theme.text_secondary};"
        )
        self.findChild(QLabel, "dimensionPreview").setStyleSheet(
            f"color: {theme.accent}; font-weight: 600;"
        )
        card = self.findChild(QFrame, "infoCard")
        card.setStyleSheet(
            f"QFrame#infoCard {{ background: {theme.bg_elevated}; border: 1px solid {theme.border}; border-radius: 8px; }}"
        )
        self.setStyleSheet(
            self.styleSheet()
            + f"QComboBox, QSpinBox {{ background: {theme.bg_input}; color: {theme.text_primary}; border: 1px solid {theme.border}; border-radius: 4px; padding: 5px 8px; }}"
            + f"QComboBox:focus, QSpinBox:focus {{ border-color: {theme.accent}; }}"
            + f"QPushButton {{ background: {theme.bg_panel}; color: {theme.text_primary}; border: 1px solid {theme.border}; border-radius: 6px; padding: 7px 18px; }}"
            + f"QPushButton#dialogButtonPrimary {{ background: {theme.accent}; color: #ffffff; border-color: {theme.accent}; font-weight: 600; }}"
            + f"QPushButton#dialogButtonPrimary:hover {{ background: {theme.accent_hover}; border-color: {theme.accent_hover}; }}"
        )