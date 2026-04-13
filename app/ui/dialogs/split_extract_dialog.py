from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeColors


@dataclass
class SplitExtractRequest:
    mode: str
    page_range_text: str
    split_size: int
    save_to_current_location: bool
    split_file_name_template: str


class SplitExtractDialog(QDialog):
    MODE_CURRENT = "current"
    MODE_RANGE = "range"
    MODE_SPLIT = "split"

    def __init__(
        self,
        source_path: str,
        current_page: int,
        page_count: int,
        theme: ThemeColors,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._source_path = Path(source_path)
        self._current_page = current_page
        self._page_count = page_count
        self._theme = theme

        self.setWindowTitle("Split / Extract Pages")
        self.setModal(True)
        self.setMinimumWidth(640)

        self._build_ui()
        self._apply_style()
        self._refresh_ui_state()

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        # --- header row (icon placeholder + title/subtitle) --------------------
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_label = QLabel("Split / Extract Pages", self)
        title_label.setObjectName("dialogTitle")
        subtitle_label = QLabel(
            f"Source: {self._source_path.name}   ·   {self._page_count} pages total",
            self,
        )
        subtitle_label.setObjectName("dialogSubtitle")
        title_col.addWidget(title_label)
        title_col.addWidget(subtitle_label)
        header_row.addLayout(title_col, 1)
        root.addLayout(header_row)

        # --- description -------------------------------------------------------
        desc = QLabel(
            "Choose how to extract pages: copy a single page, a custom range, "
            "or split the whole document into equal-size parts.",
            self,
        )
        desc.setWordWrap(True)
        desc.setObjectName("dialogDesc")
        root.addWidget(desc)

        # --- mode card (info card matching About dialog style) -----------------
        self._mode_card = QFrame(self)
        self._mode_card.setObjectName("infoCard")
        mode_layout = QVBoxLayout(self._mode_card)
        mode_layout.setContentsMargins(14, 12, 14, 12)
        mode_layout.setSpacing(12)

        section_label = QLabel("Extraction mode", self._mode_card)
        section_label.setObjectName("cardSectionLabel")
        mode_layout.addWidget(section_label)

        # Option 1 — current page
        self.extract_current_radio = QRadioButton(
            f"Extract current page  (page {self._current_page + 1})",
            self._mode_card,
        )
        self.extract_current_radio.setChecked(True)
        mode_layout.addWidget(self.extract_current_radio)

        # Option 2 — page range
        range_row = QHBoxLayout()
        range_row.setSpacing(10)
        self.extract_range_radio = QRadioButton("Extract page range:", self._mode_card)
        self.page_range_input = QLineEdit(self._mode_card)
        self.page_range_input.setPlaceholderText("e.g.  1, 3, 5-7")
        self.page_range_input.setMinimumWidth(160)
        range_row.addWidget(self.extract_range_radio)
        range_row.addWidget(self.page_range_input, 1)
        mode_layout.addLayout(range_row)

        range_hint = QLabel(
            "Enter page numbers or ranges separated by commas  —  e.g. 1,3,5-7 "
            "extracts pages 1, 3, 5, 6, 7.",
            self._mode_card,
        )
        range_hint.setObjectName("hintLabel")
        range_hint.setWordWrap(True)
        range_hint.setIndent(28)
        mode_layout.addWidget(range_hint)

        # Option 3 — split
        split_row = QHBoxLayout()
        split_row.setSpacing(10)
        self.split_range_radio = QRadioButton("Split by pages per file:", self._mode_card)
        self.split_range_input = QLineEdit(self._mode_card)
        self.split_range_input.setPlaceholderText("10")
        self.split_range_input.setText("10")
        self.split_range_input.setMaximumWidth(80)
        split_row.addWidget(self.split_range_radio)
        split_row.addWidget(self.split_range_input)
        split_row.addStretch(1)
        mode_layout.addLayout(split_row)

        split_hint = QLabel(
            "Example: a 52-page document split by 10 produces 6 files — "
            "5 files of 10 pages and 1 final file of 2 pages.",
            self._mode_card,
        )
        split_hint.setObjectName("hintLabel")
        split_hint.setWordWrap(True)
        split_hint.setIndent(28)
        mode_layout.addWidget(split_hint)

        root.addWidget(self._mode_card)

        # --- save location option ----------------------------------------------
        self._save_card = QFrame(self)
        self._save_card.setObjectName("infoCard")
        save_layout = QVBoxLayout(self._save_card)
        save_layout.setContentsMargins(14, 12, 14, 12)
        save_layout.setSpacing(10)

        save_section = QLabel("Output location", self._save_card)
        save_section.setObjectName("cardSectionLabel")
        save_layout.addWidget(save_section)

        self.save_to_current_checkbox = QCheckBox(
            "Save to same folder as the source file",
            self._save_card,
        )
        self.save_to_current_checkbox.setChecked(True)
        save_layout.addWidget(self.save_to_current_checkbox)

        save_hint = QLabel(
            "Unchecked  \u2192  button becomes 'Extract & Save' / 'Split & Save' "
            "so you can choose the destination folder.",
            self._save_card,
        )
        save_hint.setObjectName("hintLabel")
        save_hint.setWordWrap(True)
        save_hint.setIndent(28)
        save_layout.addWidget(save_hint)

        # --- split filename template -------------------------------------------
        tpl_section = QLabel("Split file name template:", self._save_card)
        tpl_section.setObjectName("cardSectionLabel")
        save_layout.addWidget(tpl_section)

        self.split_name_input = QLineEdit(self._save_card)
        self.split_name_input.setText(f"{self._source_path.stem}_split_{{range}}.pdf")
        self.split_name_input.setPlaceholderText("{filename}_split_{range}.pdf")
        save_layout.addWidget(self.split_name_input)

        tpl_hint = QLabel(
            "Placeholders: {filename}  {range}  {index}  {start}  {end}",
            self._save_card,
        )
        tpl_hint.setObjectName("hintLabel")
        save_layout.addWidget(tpl_hint)

        root.addWidget(self._save_card)

        # --- button row --------------------------------------------------------
        button_row = QHBoxLayout()
        button_row.setSpacing(8)
        button_row.addStretch(1)

        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setObjectName("dialogButtonSecondary")
        self.cancel_button.clicked.connect(self.reject)
        button_row.addWidget(self.cancel_button)

        self.apply_button = QPushButton("Extract", self)
        self.apply_button.setObjectName("dialogButtonPrimary")
        self.apply_button.clicked.connect(self._on_apply)
        self.apply_button.setDefault(True)
        button_row.addWidget(self.apply_button)

        root.addLayout(button_row)

        # connect signals
        self.extract_current_radio.toggled.connect(self._refresh_ui_state)
        self.extract_range_radio.toggled.connect(self._refresh_ui_state)
        self.split_range_radio.toggled.connect(self._refresh_ui_state)
        self.save_to_current_checkbox.toggled.connect(self._refresh_ui_state)

    # ----------------------------------------------------------------- styles

    def _apply_style(self) -> None:
        t = self._theme
        self.setStyleSheet(
            f"QDialog {{ background: {t.bg_panel}; color: {t.text_primary}; }}"
        )

        self.findChild(QLabel, "dialogTitle").setStyleSheet(
            f"font-size: 15pt; font-weight: 700; color: {t.text_primary};"
        )
        self.findChild(QLabel, "dialogSubtitle").setStyleSheet(
            f"font-size: 10.5pt; color: {t.text_secondary};"
        )
        self.findChild(QLabel, "dialogDesc").setStyleSheet(
            f"color: {t.text_secondary};"
        )

        card_style = (
            f"QFrame#infoCard {{"
            f"  background: {t.bg_elevated};"
            f"  border: 1px solid {t.border};"
            f"  border-radius: 10px;"
            f"}}"
        )
        self._mode_card.setStyleSheet(card_style)
        self._save_card.setStyleSheet(card_style)

        section_label_style = f"font-weight: 600; color: {t.text_secondary};"
        for label in self.findChildren(QLabel, "cardSectionLabel"):
            label.setStyleSheet(section_label_style)

        hint_style = f"color: {t.text_secondary}; font-size: 10pt;"
        for label in self.findChildren(QLabel, "hintLabel"):
            label.setStyleSheet(hint_style)

        btn_base = (
            f"QPushButton {{"
            f"  background: {t.bg_panel};"
            f"  border: 1px solid {t.border};"
            f"  border-radius: 8px;"
            f"  padding: 7px 18px;"
            f"  color: {t.text_primary};"
            f"  font-weight: 500;"
            f"}}"
            f"QPushButton:hover {{"
            f"  background: {t.bg_elevated};"
            f"  border-color: {t.accent};"
            f"}}"
            f"QPushButton:focus {{"
            f"  border: 2px solid {t.accent};"
            f"}}"
        )
        btn_primary = (
            f"QPushButton#dialogButtonPrimary {{"
            f"  background: {t.accent};"
            f"  border: 1px solid {t.accent};"
            f"  border-radius: 8px;"
            f"  padding: 7px 18px;"
            f"  color: #ffffff;"
            f"  font-weight: 600;"
            f"}}"
            f"QPushButton#dialogButtonPrimary:hover {{"
            f"  background: {t.accent_hover};"
            f"  border-color: {t.accent_hover};"
            f"}}"
            f"QPushButton#dialogButtonPrimary:focus {{"
            f"  border: 2px solid {t.accent_hover};"
            f"}}"
        )
        self.cancel_button.setStyleSheet(btn_base)
        self.apply_button.setStyleSheet(btn_primary)

    # ----------------------------------------------------------------- logic

    def _refresh_ui_state(self) -> None:
        is_range_mode = self.extract_range_radio.isChecked()
        is_split_mode = self.split_range_radio.isChecked()

        self.page_range_input.setEnabled(is_range_mode)
        self.split_range_input.setEnabled(is_split_mode)
        self.split_name_input.setEnabled(is_split_mode)

        if is_split_mode:
            self.apply_button.setText("Split" if self.save_to_current_checkbox.isChecked() else "Split & Save")
        else:
            self.apply_button.setText("Extract" if self.save_to_current_checkbox.isChecked() else "Extract & Save")

    def _selected_mode(self) -> str:
        if self.extract_range_radio.isChecked():
            return self.MODE_RANGE
        if self.split_range_radio.isChecked():
            return self.MODE_SPLIT
        return self.MODE_CURRENT

    def _on_apply(self) -> None:
        mode = self._selected_mode()

        if mode == self.MODE_RANGE and not self.page_range_input.text().strip():
            QMessageBox.warning(self, "Missing Page Range", "Enter one or more pages/ranges (example: 1,3,5-7).")
            return

        if mode == self.MODE_SPLIT:
            raw = self.split_range_input.text().strip()
            if not raw.isdigit() or int(raw) <= 0:
                QMessageBox.warning(self, "Invalid Split Range", "Split range must be a positive number.")
                return
            if not self.split_name_input.text().strip():
                QMessageBox.warning(self, "Missing File Name", "Provide a split file name template.")
                return

        self.accept()

    def build_request(self) -> SplitExtractRequest:
        mode = self._selected_mode()
        split_size = int(self.split_range_input.text().strip() or "0")
        return SplitExtractRequest(
            mode=mode,
            page_range_text=self.page_range_input.text().strip(),
            split_size=split_size,
            save_to_current_location=self.save_to_current_checkbox.isChecked(),
            split_file_name_template=self.split_name_input.text().strip(),
        )

