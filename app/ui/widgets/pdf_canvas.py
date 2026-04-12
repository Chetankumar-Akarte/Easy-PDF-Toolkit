from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget


class PdfCanvas(QWidget):
    DISPLAY_MODE_CONTINUOUS = "continuous"
    DISPLAY_MODE_SINGLE = "single"

    zoom_requested = Signal(int)
    zoom_level_changed = Signal(float)
    current_page_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.zoom_level = 1.0
        self._page_images: list[QImage] = []
        self._page_source_sizes: list[tuple[int, int] | None] = []
        self._page_labels: list[QLabel] = []
        self._current_page = 0
        self._suspend_scroll_notifications = False
        self._display_mode = self.DISPLAY_MODE_CONTINUOUS
        self._night_mode = False

        self._container = QWidget(self)
        self._container.setObjectName("pdfCanvasContainer")
        self._pages_layout = QVBoxLayout(self._container)
        self._pages_layout.setContentsMargins(12, 12, 12, 12)
        self._pages_layout.setSpacing(8)
        self._pages_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

        self._scroll_area = QScrollArea(self)
        self._scroll_area.setObjectName("pdfScrollArea")
        self._scroll_area.setWidget(self._container)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.viewport().installEventFilter(self)
        self._scroll_area.installEventFilter(self)
        self._scroll_area.verticalScrollBar().valueChanged.connect(self._emit_current_page_from_scroll)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._scroll_area)

        self._apply_night_mode_style()

    def _style_loaded_page(self, label: QLabel) -> None:
        label.setObjectName("pdfPage")
        label.setProperty("nightMode", self._night_mode)
        label.style().unpolish(label)
        label.style().polish(label)

    def _style_loading_page(self, label: QLabel) -> None:
        label.setObjectName("pdfPageLoading")
        label.setProperty("nightMode", self._night_mode)
        label.style().unpolish(label)
        label.style().polish(label)

    def _apply_night_mode_style(self) -> None:
        for widget in (self._scroll_area, self._scroll_area.viewport(), self._container):
            widget.setProperty("nightMode", self._night_mode)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

        for label in self._page_labels:
            label.setProperty("nightMode", self._night_mode)
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()

    def set_night_mode(self, active: bool) -> None:
        next_mode = bool(active)
        if next_mode == self._night_mode:
            return
        self._night_mode = next_mode
        self._apply_night_mode_style()

    def set_placeholder_text(self, text: str) -> None:
        self._clear_pages()
        placeholder = QLabel(text, self._container)
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setMinimumSize(600, 300)
        self._style_loading_page(placeholder)
        self._pages_layout.addWidget(placeholder)
        self._page_labels = [placeholder]
        self._page_images = []
        self._current_page = 0

    def set_page_count(self, page_count: int, page_sizes: list[tuple[int, int]] | None = None) -> None:
        self._clear_pages()
        self._page_images = [None] * page_count
        if page_sizes is not None and len(page_sizes) == page_count:
            self._page_source_sizes = list(page_sizes)
        else:
            self._page_source_sizes = [None] * page_count
        self._page_labels = []
        self._current_page = 0

        for index in range(page_count):
            page_label = QLabel(f"Loading page {index + 1}...", self._container)
            page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            page_label.setFixedSize(600, 400)
            self._style_loading_page(page_label)
            self._pages_layout.addWidget(page_label)
            self._page_labels.append(page_label)

        self._apply_display_mode()

        if page_count > 0:
            self.current_page_changed.emit(0)

    def set_document_pages(self, images: list[QImage]) -> None:
        self._clear_pages()
        self._page_images = list(images)
        self._page_source_sizes = [(image.width(), image.height()) for image in images]
        self._page_labels = []
        self._current_page = 0

        for _ in images:
            page_label = QLabel(self._container)
            page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._style_loading_page(page_label)
            self._pages_layout.addWidget(page_label)
            self._page_labels.append(page_label)

        self._apply_display_mode()
        self._refresh_image()
        if images:
            self.current_page_changed.emit(0)

    def set_display_mode(self, mode: str) -> None:
        next_mode = mode if mode in (self.DISPLAY_MODE_CONTINUOUS, self.DISPLAY_MODE_SINGLE) else self.DISPLAY_MODE_CONTINUOUS
        if next_mode == self._display_mode:
            return

        self._display_mode = next_mode
        self._apply_display_mode()
        self._resize_container_from_labels()

    def set_page_image(self, page_index: int, image: QImage) -> None:
        if page_index < 0 or page_index >= len(self._page_images):
            return

        should_anchor = self._display_mode == self.DISPLAY_MODE_SINGLE or page_index == self._current_page
        if should_anchor:
            anchor_index, anchor_ratio = self._capture_viewport_anchor()
        self._page_images[page_index] = image
        self._apply_page_image(page_index)
        self._resize_container_from_labels()
        if should_anchor:
            self._restore_viewport_anchor(anchor_index, anchor_ratio)

    def clear_page_image(self, page_index: int) -> None:
        if page_index < 0 or page_index >= len(self._page_images):
            return
        if self._page_images[page_index] is None:
            return

        should_anchor = self._display_mode == self.DISPLAY_MODE_SINGLE or page_index == self._current_page
        if should_anchor:
            anchor_index, anchor_ratio = self._capture_viewport_anchor()
        self._page_images[page_index] = None

        label = self._page_labels[page_index]
        width, height = self._scaled_size_for_page(page_index)
        label.setText(f"Loading page {page_index + 1}...")
        label.setPixmap(QPixmap())
        self._style_loading_page(label)
        label.setMinimumSize(width, height)
        label.setFixedSize(width, height)

        self._resize_container_from_labels()
        if should_anchor:
            self._restore_viewport_anchor(anchor_index, anchor_ratio)

    def zoom_in(self) -> None:
        self._set_zoom_level_internal(min(self.zoom_level + 0.1, 4.0))

    def zoom_out(self) -> None:
        self._set_zoom_level_internal(max(self.zoom_level - 0.1, 0.2))

    def set_zoom_level(self, zoom_level: float) -> None:
        bounded_zoom = max(0.2, min(zoom_level, 4.0))
        self._set_zoom_level_internal(bounded_zoom)

    def fit_current_page_to_height(self) -> None:
        if not self._page_images:
            return

        page_index = max(0, min(self._current_page, len(self._page_images) - 1))
        source_size = self._page_source_sizes[page_index]
        if source_size is None:
            return

        margins = self._pages_layout.contentsMargins()
        available_height = max(
            self._scroll_area.viewport().height() - margins.top() - margins.bottom(),
            1,
        )
        image_height = max(source_size[1], 1)
        target_zoom = max(0.2, min(available_height / image_height, 4.0))
        self.set_zoom_level(target_zoom)

    def fit_current_page_to_width(self) -> None:
        if not self._page_images:
            return

        page_index = max(0, min(self._current_page, len(self._page_images) - 1))
        source_size = self._page_source_sizes[page_index]
        if source_size is None:
            return

        margins = self._pages_layout.contentsMargins()
        safety_padding = 8
        available_width = max(
            self._scroll_area.viewport().width() - margins.left() - margins.right() - safety_padding,
            1,
        )
        image_width = max(source_size[0], 1)
        target_zoom = max(0.2, min(available_width / image_width, 4.0))
        self.set_zoom_level(target_zoom)

    def scroll_to_page(self, page_index: int) -> None:
        if page_index < 0 or page_index >= len(self._page_labels):
            return

        if self._display_mode == self.DISPLAY_MODE_SINGLE:
            self._current_page = page_index
            self._apply_display_mode()
            self._resize_container_from_labels()
            vertical_bar = self._scroll_area.verticalScrollBar()
            self._suspend_scroll_notifications = True
            vertical_bar.setValue(vertical_bar.minimum())
            self._suspend_scroll_notifications = False
            self.current_page_changed.emit(page_index)
            return

        target = self._page_labels[page_index]
        vertical_bar = self._scroll_area.verticalScrollBar()
        target_value = max(vertical_bar.minimum(), min(target.y(), vertical_bar.maximum()))
        self._suspend_scroll_notifications = True
        vertical_bar.setValue(target_value)
        self._suspend_scroll_notifications = False
        self._current_page = page_index
        self.current_page_changed.emit(page_index)

    def current_page(self) -> int:
        return self._current_page

    def _refresh_image(self) -> None:
        if not self._page_images:
            return

        for index in range(len(self._page_images)):
            self._apply_page_image(index)

        self._resize_container_from_labels()

    def _set_zoom_level_internal(self, new_zoom_level: float) -> None:
        if abs(new_zoom_level - self.zoom_level) < 1e-6:
            return

        anchor_index = self._current_page
        scroll_bar = self._scroll_area.verticalScrollBar()
        scroll_value = scroll_bar.value()
        offset_ratio = 0.0

        if 0 <= anchor_index < len(self._page_labels):
            anchor_label = self._page_labels[anchor_index]
            anchor_height = max(anchor_label.height(), 1)
            offset_ratio = (scroll_value - anchor_label.y()) / anchor_height

        self.zoom_level = new_zoom_level
        self._refresh_image()
        self.zoom_level_changed.emit(self.zoom_level)

        if 0 <= anchor_index < len(self._page_labels):
            anchor_label = self._page_labels[anchor_index]
            target_value = anchor_label.y() + int(offset_ratio * max(anchor_label.height(), 1))
            target_value = max(scroll_bar.minimum(), min(target_value, scroll_bar.maximum()))
            self._suspend_scroll_notifications = True
            scroll_bar.setValue(target_value)
            self._suspend_scroll_notifications = False

    def _apply_page_image(self, page_index: int) -> None:
        page_image = self._page_images[page_index]
        label = self._page_labels[page_index]
        if page_image is None:
            width, height = self._scaled_size_for_page(page_index)
            label.setText(f"Loading page {page_index + 1}...")
            label.setPixmap(QPixmap())
            self._style_loading_page(label)
            label.setMinimumSize(width, height)
            label.setFixedSize(width, height)
            return

        base_pixmap = QPixmap.fromImage(page_image)
        width, height = self._scaled_size_for_page(page_index)
        dpr = max(base_pixmap.devicePixelRatio(), 1.0)
        logical_size = base_pixmap.deviceIndependentSize().toSize()
        if logical_size.width() != width or logical_size.height() != height:
            base_pixmap = base_pixmap.scaled(
                max(int(width * dpr), 1),
                max(int(height * dpr), 1),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            base_pixmap.setDevicePixelRatio(dpr)

        label.setText("")
        label.setPixmap(base_pixmap)
        self._style_loaded_page(label)
        label.setFixedSize(width, height)

    def _scaled_size_for_page(self, page_index: int) -> tuple[int, int]:
        source_size = self._page_source_sizes[page_index]
        if source_size is None:
            return 600, 400

        width = max(int(source_size[0] * self.zoom_level), 1)
        height = max(int(source_size[1] * self.zoom_level), 1)
        return width, height

    def _resize_container_from_labels(self) -> None:
        total_height = 0
        max_width = 0
        visible_labels = [label for label in self._page_labels if label.isVisible()]
        for label in visible_labels:
            total_height += label.height()
            max_width = max(max_width, label.width())

        margins = self._pages_layout.contentsMargins()
        total_height += max(len(visible_labels) - 1, 0) * self._pages_layout.spacing()
        total_height += margins.top() + margins.bottom()
        total_width = max_width + margins.left() + margins.right()
        self._container.setMinimumSize(total_width, total_height)

        horizontal_bar = self._scroll_area.horizontalScrollBar()
        horizontal_bar.blockSignals(True)
        horizontal_bar.setValue(horizontal_bar.minimum())
        horizontal_bar.blockSignals(False)

    def _emit_current_page_from_scroll(self) -> None:
        if self._suspend_scroll_notifications:
            return

        if self._display_mode == self.DISPLAY_MODE_SINGLE:
            return

        if not self._page_labels:
            return

        scroll_top = self._scroll_area.verticalScrollBar().value()
        viewport_middle = scroll_top + self._scroll_area.viewport().height() // 2

        closest_index = 0
        best_distance = None
        for index, label in enumerate(self._page_labels):
            center_y = label.y() + label.height() // 2
            distance = abs(center_y - viewport_middle)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                closest_index = index

        if closest_index != self._current_page:
            self._current_page = closest_index
            self.current_page_changed.emit(closest_index)

    def _apply_display_mode(self) -> None:
        if not self._page_labels:
            return

        for index, label in enumerate(self._page_labels):
            if self._display_mode == self.DISPLAY_MODE_SINGLE:
                label.setVisible(index == self._current_page)
            else:
                label.setVisible(True)

    def _clear_pages(self) -> None:
        while self._pages_layout.count():
            item = self._pages_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._page_labels = []
        self._page_source_sizes = []

    def _capture_viewport_anchor(self) -> tuple[int, float]:
        if not self._page_labels:
            return 0, 0.0

        scroll_top = self._scroll_area.verticalScrollBar().value()
        anchor_index = 0
        for index, label in enumerate(self._page_labels):
            if label.y() + label.height() >= scroll_top:
                anchor_index = index
                break

        anchor_label = self._page_labels[anchor_index]
        anchor_height = max(anchor_label.height(), 1)
        anchor_ratio = (scroll_top - anchor_label.y()) / anchor_height
        return anchor_index, anchor_ratio

    def _restore_viewport_anchor(self, anchor_index: int, anchor_ratio: float) -> None:
        if not (0 <= anchor_index < len(self._page_labels)):
            return

        scroll_bar = self._scroll_area.verticalScrollBar()
        anchor_label = self._page_labels[anchor_index]
        target_value = anchor_label.y() + int(anchor_ratio * max(anchor_label.height(), 1))
        target_value = max(scroll_bar.minimum(), min(target_value, scroll_bar.maximum()))
        self._suspend_scroll_notifications = True
        scroll_bar.setValue(target_value)
        self._suspend_scroll_notifications = False

    def eventFilter(self, watched, event):  # noqa: N802
        if event.type() == QEvent.Type.Wheel and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_requested.emit(1)
            elif delta < 0:
                self.zoom_requested.emit(-1)
            return True
        return super().eventFilter(watched, event)
