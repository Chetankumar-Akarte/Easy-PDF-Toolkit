from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.core.services.annotation_service import AnnotationInfo


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

    def show_annotation(self, annotation: AnnotationInfo) -> None:
        kind_label = "Sticky Note" if annotation.kind == "text" else annotation.kind.title()
        color = tuple(round(channel * 255) for channel in annotation.color)
        content = annotation.content or "No associated text"
        self.selection_type_label.setText(
            f"{kind_label} annotation · Page {annotation.page_index + 1}"
        )
        self.selection_details_label.setText(
            f"Color: rgb{color}\nOpacity: {annotation.opacity:.0%}\n\n{content}"
        )
