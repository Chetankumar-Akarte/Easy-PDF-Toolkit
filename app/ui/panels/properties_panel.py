from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PropertiesPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("propertiesPanel")
        self.setMinimumWidth(240)
        layout = QVBoxLayout(self)
        title = QLabel("Properties")
        title.setObjectName("propertiesTitle")
        layout.addWidget(title)
        self.selection_type_label = QLabel("No selection")
        self.selection_type_label.setObjectName("propertiesSelectionType")
        layout.addWidget(self.selection_type_label)
        self.selection_details_label = QLabel("Select text to add PDF markup.")
        self.selection_details_label.setObjectName("propertiesSelectionDetails")
        self.selection_details_label.setWordWrap(True)
        self.selection_details_label.setTextInteractionFlags(
            self.selection_details_label.textInteractionFlags()
        )
        layout.addWidget(self.selection_details_label)
        layout.addStretch()

    def show_text_selection(self, page_number: int, text: str) -> None:
        word_count = len(text.split())
        self.selection_type_label.setText(f"Text selection · Page {page_number}")
        self.selection_details_label.setText(
            f"{word_count} word{'s' if word_count != 1 else ''}\n\n{text}"
        )

    def clear_selection(self) -> None:
        self.selection_type_label.setText("No selection")
        self.selection_details_label.setText("Select text to add PDF markup.")
