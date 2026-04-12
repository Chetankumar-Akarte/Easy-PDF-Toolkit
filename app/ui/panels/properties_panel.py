from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PropertiesPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("propertiesPanel")
        self.setMinimumWidth(240)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Properties"))
        layout.addWidget(QLabel("Selection details and annotation controls will appear here."))
        layout.addStretch()
