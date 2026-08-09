from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import ThemeColors


@dataclass(frozen=True)
class MergeDialogSource:
    path: str
    page_count: int
    page_range_text: str = "All"


@dataclass(frozen=True)
class MergePdfRequest:
    sources: tuple[MergeDialogSource, ...]
    output_path: str
    open_result: bool


class MergeSourceTable(QTableWidget):
    files_dropped = Signal(list)
    row_move_requested = Signal(int, int)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() or event.source() is self:
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls() or event.source() is self:
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            paths = [
                url.toLocalFile()
                for url in event.mimeData().urls()
                if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() == ".pdf"
            ]
            if paths:
                self.files_dropped.emit(paths)
                event.acceptProposedAction()
                return
        if event.source() is self:
            source_row = self.currentRow()
            target_row = self.rowAt(int(event.position().y()))
            if target_row < 0:
                target_row = self.rowCount() - 1
            if source_row >= 0 and target_row >= 0 and source_row != target_row:
                self.row_move_requested.emit(source_row, target_row)
            event.acceptProposedAction()
            return
        event.ignore()


class MergePdfDialog(QDialog):
    PATH_ROLE = int(Qt.ItemDataRole.UserRole)

    def __init__(
        self,
        page_count_loader: Callable[[str], int],
        theme: ThemeColors,
        initial_paths: list[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._page_count_loader = page_count_loader
        self._theme = theme

        self.setWindowTitle("Merge PDFs")
        self.setModal(True)
        self.setMinimumSize(760, 520)
        self._build_ui()
        self._apply_style()
        self.add_files(initial_paths or [], show_errors=False)
        self._update_summary()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(12)

        title = QLabel("Merge PDFs", self)
        title.setObjectName("dialogTitle")
        root.addWidget(title)
        subtitle = QLabel(
            "Arrange files in output order and optionally select pages from each PDF.",
            self,
        )
        subtitle.setObjectName("dialogSubtitle")
        root.addWidget(subtitle)

        source_card = QFrame(self)
        source_card.setObjectName("infoCard")
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(12, 12, 12, 12)
        source_layout.setSpacing(8)

        self.source_table = MergeSourceTable(0, 3, source_card)
        self.source_table.setObjectName("mergeSourceTable")
        self.source_table.setHorizontalHeaderLabels(["PDF", "Pages", "Page range"])
        self.source_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.source_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.source_table.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.source_table.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.source_table.setDropIndicatorShown(True)
        self.source_table.verticalHeader().setVisible(False)
        header = self.source_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.source_table.itemChanged.connect(self._update_summary)
        self.source_table.files_dropped.connect(self.add_files)
        self.source_table.row_move_requested.connect(self._move_row)
        source_layout.addWidget(self.source_table, 1)

        source_buttons = QHBoxLayout()
        source_buttons.setSpacing(6)
        self.add_button = QPushButton("Add PDFs", source_card)
        self.remove_button = QPushButton("Remove", source_card)
        self.move_up_button = QPushButton("Move Up", source_card)
        self.move_down_button = QPushButton("Move Down", source_card)
        self.add_button.clicked.connect(self._choose_files)
        self.remove_button.clicked.connect(self._remove_selected)
        self.move_up_button.clicked.connect(lambda: self._move_selected(-1))
        self.move_down_button.clicked.connect(lambda: self._move_selected(1))
        source_buttons.addWidget(self.add_button)
        source_buttons.addWidget(self.remove_button)
        source_buttons.addStretch(1)
        source_buttons.addWidget(self.move_up_button)
        source_buttons.addWidget(self.move_down_button)
        source_layout.addLayout(source_buttons)
        root.addWidget(source_card, 1)

        output_card = QFrame(self)
        output_card.setObjectName("infoCard")
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(12, 12, 12, 12)
        output_layout.setSpacing(8)
        output_label = QLabel("Output PDF", output_card)
        output_label.setObjectName("cardSectionLabel")
        output_layout.addWidget(output_label)
        output_row = QHBoxLayout()
        self.output_input = QLineEdit(output_card)
        self.output_input.setPlaceholderText("Choose where to save the merged PDF")
        self.browse_button = QPushButton("Browse", output_card)
        self.browse_button.clicked.connect(self._choose_output)
        output_row.addWidget(self.output_input, 1)
        output_row.addWidget(self.browse_button)
        output_layout.addLayout(output_row)
        self.open_result_checkbox = QCheckBox("Open merged PDF when complete", output_card)
        self.open_result_checkbox.setChecked(True)
        output_layout.addWidget(self.open_result_checkbox)
        root.addWidget(output_card)

        footer = QHBoxLayout()
        self.summary_label = QLabel(self)
        self.summary_label.setObjectName("mergeSummary")
        footer.addWidget(self.summary_label, 1)
        cancel_button = QPushButton("Cancel", self)
        cancel_button.clicked.connect(self.reject)
        self.merge_button = QPushButton("Merge", self)
        self.merge_button.setObjectName("dialogButtonPrimary")
        self.merge_button.setDefault(True)
        self.merge_button.clicked.connect(self._validate_and_accept)
        footer.addWidget(cancel_button)
        footer.addWidget(self.merge_button)
        root.addLayout(footer)

    def add_files(self, paths: list[str], show_errors: bool = True) -> None:
        existing = {
            str(Path(self.source_table.item(row, 0).data(self.PATH_ROLE)).resolve())
            for row in range(self.source_table.rowCount())
        }
        failures: list[str] = []
        for path_text in paths:
            path = Path(path_text).expanduser().resolve()
            if str(path) in existing:
                continue
            try:
                page_count = self._page_count_loader(str(path))
            except Exception:
                failures.append(path.name)
                continue
            if page_count <= 0:
                failures.append(path.name)
                continue

            row = self.source_table.rowCount()
            self.source_table.insertRow(row)
            name_item = QTableWidgetItem(path.name)
            name_item.setData(self.PATH_ROLE, str(path))
            name_item.setToolTip(str(path))
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            count_item = QTableWidgetItem(str(page_count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            range_item = QTableWidgetItem("All")
            range_item.setToolTip("Use All or ranges such as 1,3,5-7")
            self.source_table.setItem(row, 0, name_item)
            self.source_table.setItem(row, 1, count_item)
            self.source_table.setItem(row, 2, range_item)
            existing.add(str(path))

            if not self.output_input.text():
                self.output_input.setText(str(path.parent / f"{path.stem}_merged.pdf"))

        if failures and show_errors:
            QMessageBox.warning(
                self,
                "Could Not Add PDFs",
                "These files could not be opened as non-empty PDFs:\n" + "\n".join(failures),
            )
        self._update_summary()

    def sources(self) -> tuple[MergeDialogSource, ...]:
        return tuple(
            MergeDialogSource(
                path=str(self.source_table.item(row, 0).data(self.PATH_ROLE)),
                page_count=int(self.source_table.item(row, 1).text()),
                page_range_text=self.source_table.item(row, 2).text().strip(),
            )
            for row in range(self.source_table.rowCount())
        )

    def build_request(self) -> MergePdfRequest:
        return MergePdfRequest(
            sources=self.sources(),
            output_path=self.output_input.text().strip(),
            open_result=self.open_result_checkbox.isChecked(),
        )

    def _choose_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Add PDFs to Merge", "", "PDF files (*.pdf)")
        if paths:
            self.add_files(paths)

    def _choose_output(self) -> None:
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save Merged PDF",
            self.output_input.text(),
            "PDF files (*.pdf)",
        )
        if selected:
            path = Path(selected)
            self.output_input.setText(str(path if path.suffix.lower() == ".pdf" else path.with_suffix(".pdf")))

    def _remove_selected(self) -> None:
        row = self.source_table.currentRow()
        if row >= 0:
            self.source_table.removeRow(row)
            self._update_summary()

    def _move_selected(self, offset: int) -> None:
        row = self.source_table.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= self.source_table.rowCount():
            return
        values = [self.source_table.takeItem(row, column) for column in range(3)]
        target_values = [self.source_table.takeItem(target, column) for column in range(3)]
        for column in range(3):
            self.source_table.setItem(row, column, target_values[column])
            self.source_table.setItem(target, column, values[column])
        self.source_table.selectRow(target)
        self._update_summary()

    def _move_row(self, source: int, target: int) -> None:
        if source < 0 or target < 0 or source == target:
            return
        items = [self.source_table.takeItem(source, column) for column in range(3)]
        self.source_table.removeRow(source)
        target = min(target, self.source_table.rowCount())
        self.source_table.insertRow(target)
        for column, item in enumerate(items):
            self.source_table.setItem(target, column, item)
        self.source_table.selectRow(target)
        self._update_summary()

    def _update_summary(self) -> None:
        file_count = self.source_table.rowCount()
        page_count = sum(
            int(self.source_table.item(row, 1).text())
            for row in range(file_count)
            if self.source_table.item(row, 1) is not None
        )
        self.summary_label.setText(f"{file_count} PDFs · up to {page_count} pages")
        self.merge_button.setEnabled(file_count >= 2)

    def _validate_and_accept(self) -> None:
        sources = self.sources()
        if len(sources) < 2:
            QMessageBox.warning(self, "Add PDFs", "Add at least two PDFs to merge.")
            return
        if any(not source.page_range_text for source in sources):
            QMessageBox.warning(self, "Missing Page Range", "Use All or enter a page range for every PDF.")
            return
        output_text = self.output_input.text().strip()
        if not output_text:
            QMessageBox.warning(self, "Missing Output", "Choose an output PDF path.")
            return
        destination = Path(output_text).expanduser().resolve()
        if destination.suffix.lower() != ".pdf":
            destination = destination.with_suffix(".pdf")
            self.output_input.setText(str(destination))
        if destination in {Path(source.path).resolve() for source in sources}:
            QMessageBox.warning(self, "Invalid Output", "The output must not overwrite an input PDF.")
            return
        self.accept()

    def _apply_style(self) -> None:
        theme = self._theme
        self.findChild(QLabel, "dialogTitle").setStyleSheet(
            f"font-size: 15pt; font-weight: 700; color: {theme.text_primary};"
        )
        self.findChild(QLabel, "dialogSubtitle").setStyleSheet(f"color: {theme.text_secondary};")
        self.findChild(QLabel, "mergeSummary").setStyleSheet(
            f"color: {theme.accent}; font-weight: 600;"
        )
        self.setStyleSheet(
            f"QDialog {{ background: {theme.bg_panel}; color: {theme.text_primary}; }}"
            f"QLabel, QCheckBox {{ color: {theme.text_primary}; }}"
            f"QFrame#infoCard {{ background: {theme.bg_elevated}; border: 1px solid {theme.border}; border-radius: 8px; }}"
            f"QTableWidget, QLineEdit {{ background: {theme.bg_input}; color: {theme.text_primary}; border: 1px solid {theme.border}; }}"
            f"QHeaderView::section {{ background: {theme.bg_panel}; color: {theme.text_primary}; border: none; border-right: 1px solid {theme.border}; border-bottom: 1px solid {theme.border}; padding: 4px; }}"
            f"QTableWidget::item:selected {{ background: {theme.accent}; color: #ffffff; }}"
            f"QPushButton {{ background: {theme.bg_panel}; color: {theme.text_primary}; border: 1px solid {theme.border}; border-radius: 6px; padding: 7px 14px; }}"
            f"QPushButton:hover {{ border-color: {theme.accent}; }}"
            f"QPushButton#dialogButtonPrimary {{ background: {theme.accent}; color: #ffffff; border-color: {theme.accent}; font-weight: 600; }}"
            f"QPushButton#dialogButtonPrimary:hover {{ background: {theme.accent_hover}; }}"
        )