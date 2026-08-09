from __future__ import annotations

import sys
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QByteArray, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFontDatabase, QGuiApplication, QIcon, QImage, QKeySequence, QPainter, QPen, QPixmap, QShortcut
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QGraphicsOpacityEffect,
    QSpinBox,
    QSplitter,
    QTabBar,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.services.document_service import DocumentService
from app.core.commands import (
    Command,
    CommandHistory,
    DeletePageCommand,
    InsertBlankPagesCommand,
    ReorderPagesCommand,
    RotatePageCommand,
)
from app.core.services.page_service import MergeCancelledError, MergeSource, PageService
from app.core.services.viewer_service import SearchMatch, ViewerService
from app.infra.pdf_engines.pymupdf_adapter import PyMuPDFAdapter
from app.infra.storage.recent_files_repo import RecentFilesRepository
from app.infra.storage.settings_repo import AppSettings, SettingsRepository
from app.ui.dialogs import InsertBlankPageDialog, MergePdfDialog, SplitExtractDialog
from app.ui.panels.properties_panel import PropertiesPanel
from app.ui.theme import ThemeColors, build_qss, get_theme, make_palette
from app.ui.widgets.pdf_canvas import PdfCanvas


@dataclass
class DocumentSession:
    path: str
    document: object
    canvas: PdfCanvas
    page_count: int
    page_sizes: list[tuple[int, int]]
    current_page: int = 0
    initial_fit_applied: bool = False
    page_cache: dict[int, object] = field(default_factory=dict)
    thumbnail_cache: dict[int, QIcon] = field(default_factory=dict)
    render_queue: list[int] = field(default_factory=list)
    thumbnail_queue: list[int] = field(default_factory=list)
    search_query: str = ""
    search_matches: list[SearchMatch] = field(default_factory=list)
    active_search_match: int = -1
    is_dirty: bool = False
    command_history: CommandHistory = field(default_factory=CommandHistory)


class MainWindow(QMainWindow):
    APP_VERSION = "1.0.0"
    REPOSITORY_URL = "https://github.com/Chetankumar-Akarte/Easy-PDF-Toolkit"
    THUMBNAIL_WIDTH = 110
    THUMBNAIL_HEIGHT = 150
    THUMBNAIL_CACHE_LIMIT = 96
    THUMBNAIL_LOADING_ROLE = int(Qt.ItemDataRole.UserRole) + 1
    PRIORITY_RENDER_RADIUS = 2
    VIRTUAL_RENDER_RADIUS = 5
    PAGE_CACHE_LIMIT = 18
    FIT_MODE_WIDTH = "width"
    FIT_MODE_MANUAL = "manual"
    DISPLAY_MODE_CONTINUOUS = "continuous"
    DISPLAY_MODE_SINGLE = "single"

    def __init__(self, settings_repo: SettingsRepository, recent_files_repo: RecentFilesRepository) -> None:
        super().__init__()
        self.settings_repo = settings_repo
        self.recent_files_repo = recent_files_repo
        self._settings = self.settings_repo.load()
        self._theme: ThemeColors = get_theme(self._settings.theme)
        self._icon_cache: dict[tuple[str, str], QIcon] = {}
        self._tinted_icon_cache: dict[tuple[str, str, str], QIcon] = {}
        self._suspend_canvas_page_sync = False
        self._fit_mode = self.FIT_MODE_WIDTH
        self._display_mode = self.DISPLAY_MODE_CONTINUOUS
        self._night_reading_mode = bool(self._settings.night_mode)
        self.document_service = DocumentService()
        self.page_service = PageService()
        self.viewer_service = ViewerService()
        self.pdf_adapter = PyMuPDFAdapter()
        self._sessions_by_tab_index: dict[int, DocumentSession] = {}
        self._background_render_timer = QTimer(self)
        self._background_render_timer.setInterval(0)
        self._background_render_timer.timeout.connect(self._process_background_render_step)
        self._thumbnail_progress_angle = 0
        self._thumbnail_progress_timer = QTimer(self)
        self._thumbnail_progress_timer.setInterval(90)
        self._thumbnail_progress_timer.timeout.connect(self._animate_thumbnail_progress)
        self._search_debounce_timer = QTimer(self)
        self._search_debounce_timer.setSingleShot(True)
        self._search_debounce_timer.setInterval(250)
        self._search_debounce_timer.timeout.connect(self._perform_search)
        self._search_scan_timer = QTimer(self)
        self._search_scan_timer.setInterval(0)
        self._search_scan_timer.timeout.connect(self._process_search_page)
        self._search_scan_session: DocumentSession | None = None
        self._search_scan_query = ""
        self._search_scan_page = 0
        self._build_window()
        self._build_actions()
        self._build_layout()
        self._apply_theme()
        self._apply_startup_preferences()

    def _icon(self, icon_name: str) -> QIcon:
        cache_key = (self._theme.name, icon_name)
        cached = self._icon_cache.get(cache_key)
        if cached is not None:
            return cached

        icon_path = Path(__file__).resolve().parents[1] / "resources" / "icons" / f"{icon_name}.svg"
        svg_text = icon_path.read_text(encoding="utf-8")
        svg_text = svg_text.replace("currentColor", self._theme.icon)

        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        image = QImage(24, 24, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()

        icon = QIcon(QPixmap.fromImage(image))
        self._icon_cache[cache_key] = icon
        return icon

    def _icon_tinted(self, icon_name: str, color: str) -> QIcon:
        cache_key = (self._theme.name, icon_name, color)
        cached = self._tinted_icon_cache.get(cache_key)
        if cached is not None:
            return cached

        icon_path = Path(__file__).resolve().parents[1] / "resources" / "icons" / f"{icon_name}.svg"
        svg_text = icon_path.read_text(encoding="utf-8")
        svg_text = svg_text.replace("currentColor", color)

        renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
        image = QImage(24, 24, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()

        icon = QIcon(QPixmap.fromImage(image))
        self._tinted_icon_cache[cache_key] = icon
        return icon

    @staticmethod
    def _style_icon_button(button: QToolButton) -> None:
        button.setIconSize(QSize(18, 18))
        button.setFixedSize(30, 30)
        button.setAutoRaise(False)

    @staticmethod
    def _style_action_bar_button(button: QToolButton) -> None:
        button.setIconSize(QSize(20, 20))
        button.setFixedSize(32, 32)
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

    def _build_window(self) -> None:
        self._load_app_font()
        icon_path = Path(__file__).resolve().parents[1] / "resources" / "icons" / "tool_logo.svg"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setWindowTitle("Easy PDF Tool Kit")
        if not self._restore_window_geometry(self._settings):
            self._apply_default_window_geometry()
        self.statusBar().showMessage("Ready")

    def _load_app_font(self) -> None:
        font_path = Path(__file__).resolve().parents[1] / "resources" / "fonts" / "JosefinSans-VariableFont_wght.ttf"
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))

    def _apply_default_window_geometry(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(1400, max(900, int(available.width() * 0.92)))
            height = min(900, max(600, int(available.height() * 0.92)))
            self.resize(width, height)
            self.move(
                available.x() + (available.width() - width) // 2,
                available.y() + (available.height() - height) // 2,
            )
        else:
            self.resize(1200, 760)

    def _restore_window_geometry(self, settings: AppSettings) -> bool:
        if (
            settings.window_x is None
            or settings.window_y is None
            or settings.window_width is None
            or settings.window_height is None
        ):
            return False

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(max(settings.window_width, 900), max(settings.window_height, 600))
            self.move(settings.window_x, settings.window_y)
            return True

        available = screen.availableGeometry()
        width = min(max(settings.window_width, 900), available.width())
        height = min(max(settings.window_height, 600), available.height())
        x = min(max(settings.window_x, available.x()), available.right() - width + 1)
        y = min(max(settings.window_y, available.y()), available.bottom() - height + 1)
        self.setGeometry(x, y, width, height)
        return True

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        if self._fit_mode == self.FIT_MODE_WIDTH:
            session = self._current_session()
            if session is not None and session.page_count > 0:
                self._apply_fit_width(update_status=False, align_top=False)

    def _build_actions(self) -> None:
        self.menuBar().setNativeMenuBar(False)

        self.open_action = QAction(self._icon("open_file"), "Open", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.triggered.connect(self._open_file)

        self.close_action = QAction(self._icon("close_file"), "Close", self)
        self.close_action.setShortcut(QKeySequence("Ctrl+Shift+W"))
        self.close_action.setToolTip("Close current document (Ctrl+Shift+W)")
        self.close_action.triggered.connect(self._close_current_document)

        self.save_action = QAction(self._icon("save_file"), "Save", self)
        self.save_action.setShortcut(QKeySequence.StandardKey.Save)
        self.save_action.triggered.connect(self._save_current_document)

        self.save_as_action = QAction(self._icon("save_as"), "Save As", self)
        self.save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        self.save_as_action.triggered.connect(self._save_current_document_as)

        self.clear_recent_action = QAction(self._icon("clear_recent"), "Clear Recent History", self)
        self.clear_recent_action.triggered.connect(self._clear_recent_history)

        self.merge_pdfs_action = QAction(self._icon("merge_pdf"), "Merge PDFs...", self)
        self.merge_pdfs_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        self.merge_pdfs_action.setToolTip("Merge PDFs (Ctrl+Shift+M)")
        self.merge_pdfs_action.triggered.connect(self._open_merge_pdf_dialog)

        self.search_action = QAction(self._icon("search"), "Find...", self)
        self.search_action.setShortcut(QKeySequence.StandardKey.Find)
        self.search_action.triggered.connect(self._show_search_bar)

        self.undo_action = QAction(self._icon("undo"), "Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self._undo_current_document)

        self.redo_action = QAction(self._icon("redo"), "Redo", self)
        self.redo_action.setShortcuts(
            [QKeySequence.StandardKey.Redo, QKeySequence("Ctrl+Shift+Z")]
        )
        self.redo_action.triggered.connect(self._redo_current_document)

        self.rotate_left_action = QAction(self._icon("rotate_left"), "Rotate Left", self)
        self.rotate_left_action.setShortcut(QKeySequence("Ctrl+Alt+Left"))
        self.rotate_left_action.triggered.connect(self._rotate_current_page_left)

        self.rotate_right_action = QAction(self._icon("rotate_right"), "Rotate Right", self)
        self.rotate_right_action.setShortcut(QKeySequence("Ctrl+Alt+Right"))
        self.rotate_right_action.triggered.connect(self._rotate_current_page_right)

        self.delete_page_action = QAction(self._icon("delete_page"), "Delete Page", self)
        self.delete_page_action.setShortcut(QKeySequence("Ctrl+D"))
        self.delete_page_action.triggered.connect(self._delete_current_page)

        self.insert_blank_page_action = QAction(self._icon("insert_blank_page"), "Insert Blank Pages...", self)
        self.insert_blank_page_action.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.insert_blank_page_action.triggered.connect(self._open_insert_blank_page_dialog)

        self.toggle_thumbnail_action = QAction(self._icon("thumbnail_panel"), "Thumbnails (Ctrl+T)", self)
        self.toggle_thumbnail_action.setCheckable(True)
        self.toggle_thumbnail_action.setChecked(True)
        self.toggle_thumbnail_action.setShortcut(QKeySequence("Ctrl+T"))
        self.toggle_thumbnail_action.toggled.connect(self._set_thumbnail_panel_visible)

        self.split_extract_action = QAction(self._icon("split_extract"), "Split / Extract Pages...", self)
        self.split_extract_action.setShortcut(QKeySequence("Ctrl+X"))
        self.split_extract_action.triggered.connect(self._open_split_extract_dialog)

        self.extract_images_action = QAction(self._icon("extract_image"), "Extract Images...", self)
        self.extract_images_action.setShortcut(QKeySequence("Ctrl+Shift+I"))
        self.extract_images_action.triggered.connect(self._extract_images_from_document)

        self.fit_width_action = QAction(self._icon("fit_width"), "Fit Width", self)
        self.fit_width_action.setShortcut(QKeySequence("Ctrl+W"))
        self.fit_width_action.triggered.connect(self._fit_width)

        self.night_reading_action = QAction(self._icon("night_reading"), "Night Reading Mode", self)
        self.night_reading_action.setCheckable(True)
        self.night_reading_action.setChecked(self._night_reading_mode)
        self.night_reading_action.setShortcut(QKeySequence("Ctrl+R"))
        self.night_reading_action.setToolTip("Night Reading Mode (invert colors)")
        self.night_reading_action.toggled.connect(self._toggle_night_reading_mode)

        self.toggle_toc_action = QAction(self._icon("toc_bookmarks"), "Bookmarks / TOC (Ctrl+B)", self)
        self.toggle_toc_action.setCheckable(True)
        self.toggle_toc_action.setChecked(False)
        self.toggle_toc_action.setShortcut(QKeySequence("Ctrl+B"))
        self.toggle_toc_action.toggled.connect(self._set_toc_panel_visible)

        self.toggle_theme_action = QAction(self)
        self.toggle_theme_action.setText("Light / Dark")
        self.toggle_theme_action.setShortcut(QKeySequence("Ctrl+Alt+T"))
        self.toggle_theme_action.triggered.connect(self._toggle_theme)

        self.toggle_properties_action = QAction(self._icon("properties"), "Properties", self)
        self.toggle_properties_action.setCheckable(True)
        self.toggle_properties_action.setChecked(False)
        self.toggle_properties_action.toggled.connect(self._set_properties_panel_visible)

        self.view_continuous_action = QAction(self._icon("continuous_mode"), "Continuous", self)
        self.view_continuous_action.setShortcut(QKeySequence("Ctrl+Alt+C"))
        self.view_continuous_action.triggered.connect(lambda: self._set_reader_display_mode(self.DISPLAY_MODE_CONTINUOUS))

        self.view_single_page_action = QAction(self._icon("single_page_mode"), "Single Page", self)
        self.view_single_page_action.setShortcut(QKeySequence("Ctrl+Alt+S"))
        self.view_single_page_action.triggered.connect(lambda: self._set_reader_display_mode(self.DISPLAY_MODE_SINGLE))

        self.toggle_display_mode_action = QAction(self)
        self.toggle_display_mode_action.triggered.connect(self._toggle_reader_display_mode)
        self._sync_reader_mode_ui()

        self.exit_action = QAction(self._icon("exit"), "Exit", self)
        self.exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        self.exit_action.triggered.connect(self._exit_application)

        self.about_action = QAction(self._icon("about_info"), "About", self)
        self.about_action.triggered.connect(self._show_about)

        self.file_menu = self.menuBar().addMenu("File")
        self.file_menu.addAction(self.open_action)
        self.file_menu.addAction(self.merge_pdfs_action)
        self.file_menu.addAction(self.close_action)
        self.file_menu.addAction(self.clear_recent_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.save_action)
        self.file_menu.addAction(self.save_as_action)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.exit_action)

        self.edit_menu = self.menuBar().addMenu("Edit")
        self.edit_menu.addAction(self.undo_action)
        self.edit_menu.addAction(self.redo_action)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.search_action)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.rotate_left_action)
        self.edit_menu.addAction(self.rotate_right_action)
        self.edit_menu.addAction(self.insert_blank_page_action)
        self.edit_menu.addAction(self.delete_page_action)
        self.edit_menu.addSeparator()
        self.edit_menu.addAction(self.split_extract_action)
        self.edit_menu.addAction(self.extract_images_action)

        self.view_menu = self.menuBar().addMenu("View")
        self.view_menu.addAction(self.toggle_theme_action)
        self.view_menu.addAction(self.fit_width_action)
        self.view_menu.addAction(self.night_reading_action)
        self.view_menu.addAction(self.toggle_thumbnail_action)
        self.view_menu.addAction(self.view_continuous_action)
        self.view_menu.addAction(self.view_single_page_action)
        self.view_menu.addAction(self.toggle_toc_action)
        self.view_menu.addAction(self.toggle_properties_action)

        self.help_menu = self.menuBar().addMenu("Help")
        self.help_menu.addAction(self.about_action)

        self._bind_navigation_shortcuts()
        self._sync_document_actions(page_count=0)

    def _build_layout(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)

        self.action_bar = QWidget(root)
        self.action_bar.setObjectName("actionBar")
        self.action_bar.setFixedHeight(40)
        action_bar_layout = QHBoxLayout(self.action_bar)
        action_bar_layout.setContentsMargins(8, 4, 8, 4)
        action_bar_layout.setSpacing(6)

        for action in [self.open_action, self.night_reading_action, self.save_action, self.save_as_action, self.close_action]:
            button = QToolButton(self.action_bar)
            button.setDefaultAction(action)
            button.setToolTip(action.toolTip() or action.text())
            self._style_action_bar_button(button)
            action_bar_layout.addWidget(button)

        file_separator = QFrame(self.action_bar)
        file_separator.setFrameShape(QFrame.Shape.VLine)
        file_separator.setFrameShadow(QFrame.Shadow.Sunken)
        file_separator.setFixedHeight(24)
        action_bar_layout.addWidget(file_separator)

        for action in [self.undo_action, self.redo_action]:
            button = QToolButton(self.action_bar)
            button.setDefaultAction(action)
            button.setToolTip(action.text())
            self._style_action_bar_button(button)
            action_bar_layout.addWidget(button)

        for action in [
            self.rotate_left_action,
            self.rotate_right_action,
            self.insert_blank_page_action,
            self.delete_page_action,
        ]:
            button = QToolButton(self.action_bar)
            button.setDefaultAction(action)
            button.setToolTip(action.text())
            self._style_action_bar_button(button)
            action_bar_layout.addWidget(button)

        panel_separator = QFrame(self.action_bar)
        panel_separator.setFrameShape(QFrame.Shape.VLine)
        panel_separator.setFrameShadow(QFrame.Shadow.Sunken)
        panel_separator.setFixedHeight(24)
        action_bar_layout.addWidget(panel_separator)

        self.search_button = QToolButton(self.action_bar)
        self.search_button.setDefaultAction(self.search_action)
        self.search_button.setToolTip("Find in document (Ctrl+F)")
        self._style_action_bar_button(self.search_button)
        action_bar_layout.addWidget(self.search_button)

        self.thumbnail_toggle_button = QToolButton(self.action_bar)
        self.thumbnail_toggle_button.setDefaultAction(self.toggle_thumbnail_action)
        self.thumbnail_toggle_button.setToolTip(self.toggle_thumbnail_action.text())
        self._style_action_bar_button(self.thumbnail_toggle_button)
        action_bar_layout.addWidget(self.thumbnail_toggle_button)

        self.toc_toggle_button = QToolButton(self.action_bar)
        self.toc_toggle_button.setDefaultAction(self.toggle_toc_action)
        self.toc_toggle_button.setToolTip(self.toggle_toc_action.text())
        self._style_action_bar_button(self.toc_toggle_button)
        action_bar_layout.addWidget(self.toc_toggle_button)

        split_separator = QFrame(self.action_bar)
        split_separator.setFrameShape(QFrame.Shape.VLine)
        split_separator.setFrameShadow(QFrame.Shadow.Sunken)
        split_separator.setFixedHeight(24)
        action_bar_layout.addWidget(split_separator)

        self.merge_pdfs_button = QToolButton(self.action_bar)
        self.merge_pdfs_button.setDefaultAction(self.merge_pdfs_action)
        self.merge_pdfs_button.setToolTip(self.merge_pdfs_action.toolTip())
        self._style_action_bar_button(self.merge_pdfs_button)
        action_bar_layout.addWidget(self.merge_pdfs_button)

        self.split_extract_button = QToolButton(self.action_bar)
        self.split_extract_button.setDefaultAction(self.split_extract_action)
        self.split_extract_button.setToolTip(self.split_extract_action.text())
        self._style_action_bar_button(self.split_extract_button)

        self.extract_images_button = QToolButton(self.action_bar)
        self.extract_images_button.setDefaultAction(self.extract_images_action)
        self.extract_images_button.setToolTip(self.extract_images_action.text())
        self._style_action_bar_button(self.extract_images_button)
        action_bar_layout.addWidget(self.extract_images_button)

        action_bar_layout.addWidget(self.split_extract_button)

        action_bar_layout.addStretch(1)

        theme_separator = QFrame(self.action_bar)
        theme_separator.setFrameShape(QFrame.Shape.VLine)
        theme_separator.setFrameShadow(QFrame.Shadow.Sunken)
        theme_separator.setFixedHeight(24)
        action_bar_layout.addWidget(theme_separator)

        self.theme_toggle_button = QToolButton(self.action_bar)
        self.theme_toggle_button.setDefaultAction(self.toggle_theme_action)
        self._style_action_bar_button(self.theme_toggle_button)
        action_bar_layout.addWidget(self.theme_toggle_button)

        root_layout.addWidget(self.action_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal, root)
        self.main_splitter = splitter

        self.side_panel_tabs = QTabWidget(splitter)
        self.side_panel_tabs.setObjectName("sidePanelTabs")
        self.side_panel_tabs.setTabsClosable(True)
        self.side_panel_tabs.tabCloseRequested.connect(self._on_side_panel_tab_close_requested)

        self.thumbnail_tab = QWidget(self.side_panel_tabs)
        thumbnail_layout = QVBoxLayout(self.thumbnail_tab)
        thumbnail_layout.setContentsMargins(0, 0, 0, 0)
        thumbnail_layout.setSpacing(0)

        thumbnail_header = QWidget(self.thumbnail_tab)
        thumbnail_header.setObjectName("sidePanelHeader")
        thumbnail_header_layout = QHBoxLayout(thumbnail_header)
        thumbnail_header_layout.setContentsMargins(8, 6, 6, 6)
        thumbnail_header_layout.setSpacing(4)
        self.thumbnail_header_label = QLabel("Thumbnails", thumbnail_header)
        thumbnail_header_layout.addWidget(self.thumbnail_header_label)
        thumbnail_header_layout.addStretch(1)
        self.thumbnail_close_button = QToolButton(thumbnail_header)
        self.thumbnail_close_button.setObjectName("sidePanelClose")
        self.thumbnail_close_button.setText("✕")
        self.thumbnail_close_button.setFixedSize(22, 22)
        self.thumbnail_close_button.setToolTip("Close Thumbnails")
        self.thumbnail_close_button.clicked.connect(lambda: self.toggle_thumbnail_action.setChecked(False))
        thumbnail_header_layout.addWidget(self.thumbnail_close_button)
        thumbnail_layout.addWidget(thumbnail_header)

        self.thumbnail_list = QListWidget(self.thumbnail_tab)
        self.thumbnail_list.setObjectName("thumbnailList")
        self.thumbnail_list.setMinimumWidth(170)
        self.thumbnail_list.setMaximumWidth(300)
        self.thumbnail_list.setIconSize(QSize(self.THUMBNAIL_WIDTH, self.THUMBNAIL_HEIGHT))
        self.thumbnail_list.setViewMode(QListView.ViewMode.IconMode)
        self.thumbnail_list.setFlow(QListView.Flow.TopToBottom)
        self.thumbnail_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.thumbnail_list.setWrapping(False)
        self.thumbnail_list.setWordWrap(True)
        self.thumbnail_list.setGridSize(QSize(138, 184))
        self.thumbnail_list.setSpacing(4)
        self.thumbnail_list.addItem("No document loaded")
        self.thumbnail_list.currentRowChanged.connect(self._on_thumbnail_selected)
        self.thumbnail_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.thumbnail_list.customContextMenuRequested.connect(self._show_thumbnail_context_menu)
        self.thumbnail_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.thumbnail_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.thumbnail_list.model().rowsMoved.connect(self._on_thumbnail_rows_moved)
        thumbnail_layout.addWidget(self.thumbnail_list)

        self.toc_tab = QWidget(self.side_panel_tabs)
        self.toc_tab.setObjectName("tocPanel")
        toc_layout = QVBoxLayout(self.toc_tab)
        toc_layout.setContentsMargins(0, 0, 0, 0)
        toc_layout.setSpacing(0)

        toc_header = QWidget(self.toc_tab)
        toc_header.setObjectName("tocHeader")
        toc_header_layout = QHBoxLayout(toc_header)
        toc_header_layout.setContentsMargins(8, 6, 6, 6)
        toc_header_layout.setSpacing(4)
        self.toc_header_label = QLabel("Bookmarks / TOC", toc_header)
        toc_header_layout.addWidget(self.toc_header_label)
        toc_header_layout.addStretch(1)
        self.toc_edge_toggle_button = QToolButton(toc_header)
        self.toc_edge_toggle_button.setObjectName("tocEdgeToggle")
        self.toc_edge_toggle_button.setText("✕")
        self.toc_edge_toggle_button.setFixedSize(22, 22)
        self.toc_edge_toggle_button.setToolTip("Close Bookmarks / TOC")
        self.toc_edge_toggle_button.clicked.connect(lambda: self.toggle_toc_action.setChecked(False))
        toc_header_layout.addWidget(self.toc_edge_toggle_button)
        toc_layout.addWidget(toc_header)

        self.toc_tree = QTreeWidget(self.toc_tab)
        self.toc_tree.setObjectName("tocTree")
        self.toc_tree.setHeaderHidden(True)
        self.toc_tree.setMinimumWidth(190)
        self.toc_tree.setMaximumWidth(300)
        self.toc_tree.itemClicked.connect(self._on_toc_item_clicked)
        toc_layout.addWidget(self.toc_tree)

        self.thumbnail_tab_index = self.side_panel_tabs.addTab(self.thumbnail_tab, "Thumbnails")
        self.toc_tab_index = self.side_panel_tabs.addTab(self.toc_tab, "Bookmarks / TOC")

        reader_area = QWidget(splitter)
        reader_layout = QVBoxLayout(reader_area)
        reader_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget(reader_area)
        self.tab_widget.setObjectName("documentTabs")
        self.tab_widget.setTabsClosable(False)

        self.document_close_button = QToolButton(self.tab_widget)
        self.document_close_button.setObjectName("documentCloseButton")
        self.document_close_button.setDefaultAction(self.close_action)
        self.document_close_button.setAccessibleName("Close current document")
        self._style_icon_button(self.document_close_button)
        self.tab_widget.setCornerWidget(
            self.document_close_button,
            Qt.Corner.TopRightCorner,
        )

        self.welcome_list = QListWidget(reader_area)
        self.welcome_list.setObjectName("welcomeList")
        self.welcome_list.setIconSize(QSize(28, 28))
        self.welcome_list.setSpacing(10)
        self.welcome_list.itemActivated.connect(self._open_recent_item)
        self.tab_widget.addTab(self.welcome_list, "Welcome")
        self._refresh_welcome_recent_documents()

        self.search_bar = QWidget(reader_area)
        self.search_bar.setObjectName("searchBar")
        search_layout = QHBoxLayout(self.search_bar)
        search_layout.setContentsMargins(10, 5, 10, 5)
        search_layout.setSpacing(6)
        search_layout.addStretch(1)

        self.search_input = QLineEdit(self.search_bar)
        self.search_input.setObjectName("documentSearchInput")
        self.search_input.setPlaceholderText("Find in document")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(280)
        self.search_input.setMaximumWidth(460)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.search_input.returnPressed.connect(self._go_next_search_match)
        search_layout.addWidget(self.search_input)

        self.search_result_label = QLabel("0 / 0", self.search_bar)
        self.search_result_label.setObjectName("searchResultLabel")
        self.search_result_label.setMinimumWidth(72)
        self.search_result_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        search_layout.addWidget(self.search_result_label)

        self.search_previous_button = QToolButton(self.search_bar)
        self.search_previous_button.setIcon(self._icon("prev_page"))
        self.search_previous_button.setToolTip("Previous match (Shift+Enter)")
        self.search_previous_button.clicked.connect(self._go_previous_search_match)
        self._style_icon_button(self.search_previous_button)
        search_layout.addWidget(self.search_previous_button)

        self.search_next_button = QToolButton(self.search_bar)
        self.search_next_button.setIcon(self._icon("next_page"))
        self.search_next_button.setToolTip("Next match (Enter)")
        self.search_next_button.clicked.connect(self._go_next_search_match)
        self._style_icon_button(self.search_next_button)
        search_layout.addWidget(self.search_next_button)

        self.search_close_button = QToolButton(self.search_bar)
        self.search_close_button.setIcon(self._icon("close_file"))
        self.search_close_button.setToolTip("Close search (Esc)")
        self.search_close_button.clicked.connect(self._hide_search_bar)
        self._style_icon_button(self.search_close_button)
        search_layout.addWidget(self.search_close_button)
        search_layout.addStretch(1)

        self.search_bar.setVisible(False)
        self._search_previous_shortcut = QShortcut(QKeySequence("Shift+Return"), self.search_bar)
        self._search_previous_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._search_previous_shortcut.activated.connect(self._go_previous_search_match)
        self._search_escape_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self.search_bar)
        self._search_escape_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._search_escape_shortcut.activated.connect(self._hide_search_bar)

        reader_layout.addWidget(self.search_bar)
        reader_layout.addWidget(self.tab_widget)

        self.reader_controls = QWidget(reader_area)
        self.reader_controls.setObjectName("readerControls")
        self.reader_controls.setFixedHeight(40)
        controls_layout = QHBoxLayout(self.reader_controls)
        controls_layout.setContentsMargins(8, 4, 8, 4)
        controls_layout.setSpacing(6)
        controls_layout.addStretch(1)

        self.first_page_button = QToolButton(self.reader_controls)
        self.first_page_button.setIcon(self._icon("first_page"))
        self.first_page_button.setToolTip("First page")
        self.first_page_button.clicked.connect(self._go_first_page)
        self._style_icon_button(self.first_page_button)
        controls_layout.addWidget(self.first_page_button)

        self.previous_page_button = QToolButton(self.reader_controls)
        self.previous_page_button.setIcon(self._icon("prev_page"))
        self.previous_page_button.setToolTip("Previous page")
        self.previous_page_button.clicked.connect(self._go_previous_page)
        self._style_icon_button(self.previous_page_button)
        controls_layout.addWidget(self.previous_page_button)

        self.page_spin = QSpinBox(self.reader_controls)
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setEnabled(False)
        self.page_spin.valueChanged.connect(self._on_page_spin_changed)
        controls_layout.addWidget(self.page_spin)

        self.page_total_label = QLabel("/ 0", self.reader_controls)
        controls_layout.addWidget(self.page_total_label)

        self.next_page_button = QToolButton(self.reader_controls)
        self.next_page_button.setIcon(self._icon("next_page"))
        self.next_page_button.setToolTip("Next page")
        self.next_page_button.clicked.connect(self._go_next_page)
        self._style_icon_button(self.next_page_button)
        controls_layout.addWidget(self.next_page_button)

        self.last_page_button = QToolButton(self.reader_controls)
        self.last_page_button.setIcon(self._icon("last_page"))
        self.last_page_button.setToolTip("Last page")
        self.last_page_button.clicked.connect(self._go_last_page)
        self._style_icon_button(self.last_page_button)
        controls_layout.addWidget(self.last_page_button)

        controls_layout.addSpacing(14)

        self.zoom_out_button = QToolButton(self.reader_controls)
        self.zoom_out_button.setIcon(self._icon("zoom_out"))
        self.zoom_out_button.setToolTip("Zoom out")
        self.zoom_out_button.clicked.connect(self._zoom_out)
        self._style_icon_button(self.zoom_out_button)
        controls_layout.addWidget(self.zoom_out_button)

        self.zoom_label = QLabel("100%", self.reader_controls)
        controls_layout.addWidget(self.zoom_label)

        self.zoom_in_button = QToolButton(self.reader_controls)
        self.zoom_in_button.setIcon(self._icon("zoom_in"))
        self.zoom_in_button.setToolTip("Zoom in")
        self.zoom_in_button.clicked.connect(self._zoom_in)
        self._style_icon_button(self.zoom_in_button)
        controls_layout.addWidget(self.zoom_in_button)

        self.reset_zoom_button = QToolButton(self.reader_controls)
        self.reset_zoom_button.setIcon(self._icon("reset_zoom"))
        self.reset_zoom_button.setToolTip("Reset zoom to 100%")
        self.reset_zoom_button.clicked.connect(self._reset_zoom)
        self._style_icon_button(self.reset_zoom_button)
        controls_layout.addWidget(self.reset_zoom_button)

        self.fit_width_button = QToolButton(self.reader_controls)
        self.fit_width_button.setIcon(self._icon("fit_width"))
        self.fit_width_button.setToolTip("Fit page to width")
        self.fit_width_button.clicked.connect(self._fit_width)
        self._style_icon_button(self.fit_width_button)
        controls_layout.addWidget(self.fit_width_button)

        self.display_mode_toggle_button = QToolButton(self.reader_controls)
        self.display_mode_toggle_button.setDefaultAction(self.toggle_display_mode_action)
        self._style_icon_button(self.display_mode_toggle_button)
        controls_layout.addWidget(self.display_mode_toggle_button)

        self.night_mode_badge_button = QToolButton(self.reader_controls)
        self.night_mode_badge_button.setObjectName("nightModeBadge")
        self.night_mode_badge_button.setToolTip("Night Reading Mode (invert colors)")
        self.night_mode_badge_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self._style_icon_button(self.night_mode_badge_button)
        self.night_mode_badge_button.clicked.connect(self.night_reading_action.toggle)
        controls_layout.addWidget(self.night_mode_badge_button)

        controls_layout.addStretch(1)

        reader_layout.addWidget(self.reader_controls)
        reader_layout.addSpacing(2)

        self.tab_widget.currentChanged.connect(self._on_tab_changed)

        self.properties_panel = PropertiesPanel(splitter)
        self.properties_panel.setVisible(False)

        splitter.setSizes([250, 1050, 0])
        self._set_thumbnail_panel_visible(True)
        self._set_toc_panel_visible(False)
        root_layout.addWidget(splitter)

        self.setCentralWidget(root)

    def _sync_document_actions(self, page_count: int) -> None:
        has_document = self._current_session() is not None
        has_pages = has_document and page_count > 0
        self.close_action.setEnabled(has_document)
        self.merge_pdfs_action.setEnabled(True)
        self._sync_undo_redo_actions(self._current_session())
        self.save_action.setEnabled(has_document)
        self.save_as_action.setEnabled(has_document)
        self.rotate_left_action.setEnabled(has_pages)
        self.rotate_right_action.setEnabled(has_pages)
        self.delete_page_action.setEnabled(has_pages)
        self.insert_blank_page_action.setEnabled(has_pages)
        self.split_extract_action.setEnabled(has_pages)
        self.extract_images_action.setEnabled(has_pages)
        self.search_action.setEnabled(has_pages)
        self.fit_width_action.setEnabled(has_pages)
        self.night_reading_action.setEnabled(has_document)
        self.toggle_display_mode_action.setEnabled(has_document)
        self.toggle_thumbnail_action.setEnabled(has_document)
        if hasattr(self, "night_mode_badge_button"):
            self.night_mode_badge_button.setEnabled(has_document)
        has_toc = hasattr(self, "toc_tree") and self.toc_tree.topLevelItemCount() > 0
        self.toggle_toc_action.setEnabled(has_document and has_toc)

    def _set_properties_panel_visible(self, visible: bool) -> None:
        if not hasattr(self, "properties_panel") or not hasattr(self, "main_splitter"):
            return

        self.properties_panel.setVisible(visible)
        self._update_side_panel_sizes()

    def _on_side_panel_tab_close_requested(self, index: int) -> None:
        if index == self.thumbnail_tab_index:
            self.toggle_thumbnail_action.setChecked(False)
        elif index == self.toc_tab_index:
            self.toggle_toc_action.setChecked(False)

    def _update_side_panel_sizes(self) -> None:
        if not hasattr(self, "main_splitter"):
            return

        left_visible = hasattr(self, "side_panel_tabs") and self.side_panel_tabs.isVisible()
        props_visible = hasattr(self, "properties_panel") and self.properties_panel.isVisible()

        if left_visible and props_visible:
            self.main_splitter.setSizes([250, 800, 300])
        elif left_visible and not props_visible:
            self.main_splitter.setSizes([250, 1050, 0])
        elif not left_visible and props_visible:
            self.main_splitter.setSizes([0, 1050, 300])
        else:
            self.main_splitter.setSizes([0, 1300, 0])

    def _apply_theme(self) -> None:
        self._theme = get_theme(self._settings.theme)
        QApplication.setPalette(make_palette(self._theme))
        QApplication.instance().setStyleSheet(build_qss(self._theme))
        self._icon_cache.clear()
        self._tinted_icon_cache.clear()
        self._refresh_theme_icons()

    def _toggle_theme(self) -> None:
        self._settings.theme = "dark" if self._settings.theme != "dark" else "light"
        self.settings_repo.save(self._settings)
        self._apply_theme()
        self.statusBar().showMessage(f"Theme: {self._settings.theme}")

    def _refresh_theme_icons(self) -> None:
        self.open_action.setIcon(self._icon("open_file"))
        self.merge_pdfs_action.setIcon(self._icon("merge_pdf"))
        self.close_action.setIcon(self._icon("close_file"))
        self.save_action.setIcon(self._icon("save_file"))
        self.save_as_action.setIcon(self._icon("save_as"))
        self.clear_recent_action.setIcon(self._icon("clear_recent"))
        self.search_action.setIcon(self._icon("search"))
        self.undo_action.setIcon(self._icon("undo"))
        self.redo_action.setIcon(self._icon("redo"))
        self.rotate_left_action.setIcon(self._icon("rotate_left"))
        self.rotate_right_action.setIcon(self._icon("rotate_right"))
        self.delete_page_action.setIcon(self._icon("delete_page"))
        self.insert_blank_page_action.setIcon(self._icon("insert_blank_page"))
        self.toggle_thumbnail_action.setIcon(self._icon("thumbnail_panel"))
        self.split_extract_action.setIcon(self._icon("split_extract"))
        self.extract_images_action.setIcon(self._icon("extract_image"))
        self.fit_width_action.setIcon(self._icon("fit_width"))
        self.night_reading_action.setIcon(self._icon("night_reading"))
        self.toggle_toc_action.setIcon(self._icon("toc_bookmarks"))
        self.toggle_properties_action.setIcon(self._icon("properties"))
        self.view_continuous_action.setIcon(self._icon("continuous_mode"))
        self.view_single_page_action.setIcon(self._icon("single_page_mode"))
        self.exit_action.setIcon(self._icon("exit"))
        self.about_action.setIcon(self._icon("about_info"))

        for action in (
            self.open_action,
            self.merge_pdfs_action,
            self.close_action,
            self.save_action,
            self.save_as_action,
            self.clear_recent_action,
            self.search_action,
            self.undo_action,
            self.redo_action,
            self.rotate_left_action,
            self.rotate_right_action,
            self.delete_page_action,
            self.insert_blank_page_action,
            self.toggle_thumbnail_action,
            self.split_extract_action,
            self.extract_images_action,
            self.fit_width_action,
            self.night_reading_action,
            self.toggle_toc_action,
            self.toggle_properties_action,
            self.view_continuous_action,
            self.view_single_page_action,
            self.exit_action,
            self.about_action,
        ):
            action.setIconVisibleInMenu(True)

        next_theme = "light" if self._settings.theme == "dark" else "dark"
        theme_icon = "theme_sun" if self._settings.theme == "dark" else "theme_moon"
        self.toggle_theme_action.setIcon(self._icon(theme_icon))
        self.toggle_theme_action.setIconVisibleInMenu(True)
        self.toggle_theme_action.setText("Light / Dark")
        self.toggle_theme_action.setToolTip(f"Switch to {next_theme.title()} Theme (Ctrl+Alt+T)")

        self.night_reading_action.setText("Night Reading Mode")
        self.night_reading_action.setToolTip("Night Reading Mode (invert colors)")

        if hasattr(self, "first_page_button"):
            self.first_page_button.setIcon(self._icon("first_page"))
            self.previous_page_button.setIcon(self._icon("prev_page"))
            self.next_page_button.setIcon(self._icon("next_page"))
            self.last_page_button.setIcon(self._icon("last_page"))
            self.zoom_out_button.setIcon(self._icon("zoom_out"))
            self.zoom_in_button.setIcon(self._icon("zoom_in"))
            self.reset_zoom_button.setIcon(self._icon("reset_zoom"))
            self.fit_width_button.setIcon(self._icon("fit_width"))
            self.search_previous_button.setIcon(self._icon("prev_page"))
            self.search_next_button.setIcon(self._icon("next_page"))
            self.search_close_button.setIcon(self._icon("close_file"))
            if hasattr(self, "tab_widget"):
                for tab_index in range(self.tab_widget.count()):
                    close_button = self.tab_widget.tabBar().tabButton(
                        tab_index,
                        QTabBar.ButtonPosition.RightSide,
                    )
                    if isinstance(close_button, QToolButton):
                        close_button.setIcon(self._icon("close_file"))

        self._refresh_night_badge_ui()

        if hasattr(self, "welcome_list"):
            self._refresh_welcome_recent_documents()

    def _apply_startup_preferences(self) -> None:
        recent = self.recent_files_repo.load()
        if recent:
            self.statusBar().showMessage(f"Ready | Recent files: {len(recent)}")
        if self._settings.theme == "dark":
            self.statusBar().showMessage(self.statusBar().currentMessage() + " | Theme: dark")

    def _toggle_night_reading_mode(self, enabled: bool) -> None:
        self._night_reading_mode = enabled
        self._settings.night_mode = enabled
        self.settings_repo.save(self._settings)

        self._refresh_night_badge_ui()
        self._animate_night_badge_toggle()

        current_session = self._current_session()
        if current_session is None:
            self.statusBar().showMessage("Night Reading Mode enabled" if enabled else "Night Reading Mode disabled")
            return

        for session in self._sessions_by_tab_index.values():
            session.canvas.set_night_mode(enabled)
            session.page_cache.clear()
            session.thumbnail_cache.clear()
            session.render_queue.clear()
            session.thumbnail_queue = list(range(session.page_count))
            for page_index in range(session.page_count):
                session.canvas.clear_page_image(page_index)

        self._load_thumbnails_for_current_session()
        self._queue_render_for_current_session(center_page=current_session.current_page)
        mode_label = "enabled" if enabled else "disabled"
        self.statusBar().showMessage(f"Night Reading Mode {mode_label}")

    def _refresh_night_badge_ui(self) -> None:
        if not hasattr(self, "night_mode_badge_button"):
            return
        is_active = self._night_reading_mode
        icon = self._icon_tinted("night_reading", self._theme.accent) if is_active else self._icon("night_reading")
        self.night_mode_badge_button.setIcon(icon)
        self.night_mode_badge_button.setProperty("active", is_active)
        self.night_mode_badge_button.style().unpolish(self.night_mode_badge_button)
        self.night_mode_badge_button.style().polish(self.night_mode_badge_button)

    def _animate_night_badge_toggle(self) -> None:
        if not hasattr(self, "night_mode_badge_button"):
            return

        if not hasattr(self, "_night_badge_opacity"):
            self._night_badge_opacity = QGraphicsOpacityEffect(self.night_mode_badge_button)
            self._night_badge_opacity.setOpacity(1.0)
            self.night_mode_badge_button.setGraphicsEffect(self._night_badge_opacity)

        self._night_badge_fade = QPropertyAnimation(self._night_badge_opacity, b"opacity", self)
        self._night_badge_fade.setDuration(180)
        self._night_badge_fade.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._night_badge_fade.setStartValue(0.45)
        self._night_badge_fade.setEndValue(1.0)
        self._night_badge_fade.start()

    def _open_file(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF",
            self._initial_open_directory(),
            "PDF files (*.pdf)",
        )
        if not selected:
            return
        self._open_document_by_path(selected)

    def _open_merge_pdf_dialog(self) -> None:
        session = self._current_session()
        initial_paths = [session.path] if session is not None else []
        dialog = MergePdfDialog(
            page_count_loader=self.pdf_adapter.file_page_count,
            theme=self._theme,
            initial_paths=initial_paths,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        request = dialog.build_request()
        sources: list[MergeSource] = []
        try:
            for source in request.sources:
                range_text = source.page_range_text.strip()
                page_indices = (
                    list(range(source.page_count))
                    if range_text.lower() == "all"
                    else self.page_service.parse_page_ranges(range_text, source.page_count)
                )
                sources.append(MergeSource(source.path, tuple(page_indices)))
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Page Range", str(exc))
            return

        output_path = Path(request.output_path).expanduser().resolve()
        if output_path.suffix.lower() != ".pdf":
            output_path = output_path.with_suffix(".pdf")
        if output_path.exists():
            answer = QMessageBox.question(
                self,
                "Overwrite Merged PDF",
                f"{output_path.name} already exists.\nDo you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.statusBar().showMessage("Merge cancelled")
                return

        progress_dialog = QProgressDialog("Preparing merge...", "Cancel", 0, len(sources), self)
        progress_dialog.setWindowTitle("Merging PDFs")
        progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setValue(0)

        def update_progress(current: int, total: int, name: str) -> None:
            progress_dialog.setMaximum(total)
            progress_dialog.setLabelText(f"Merged {name} ({current} of {total})")
            progress_dialog.setValue(current)
            QApplication.processEvents()

        try:
            merged_path = self.page_service.merge_pdfs(
                sources,
                str(output_path),
                progress=update_progress,
                is_cancelled=progress_dialog.wasCanceled,
            )
        except MergeCancelledError:
            self.statusBar().showMessage("Merge cancelled")
            return
        except Exception as exc:
            QMessageBox.critical(self, "Merge Failed", f"Could not merge PDFs:\n{exc}")
            return
        finally:
            progress_dialog.close()

        self.recent_files_repo.add(merged_path)
        self._settings.last_open_dir = str(Path(merged_path).parent)
        self.settings_repo.save(self._settings)
        if request.open_result:
            self._open_document_by_path(merged_path)
        self.statusBar().showMessage(
            f"Merged {len(sources)} PDFs into {Path(merged_path).name}"
        )

    def _open_document_by_path(self, selected: str) -> None:
        selected_path = str(Path(selected).resolve())

        # If the file is already open in a tab, switch to it instead of reopening.
        for idx, session in self._sessions_by_tab_index.items():
            if str(Path(session.path).resolve()) == selected_path:
                self.tab_widget.setCurrentIndex(idx)
                return

        try:
            document = self.pdf_adapter.open_document(selected_path)
            page_count = self.pdf_adapter.page_count(document)
            page_sizes = self.pdf_adapter.page_sizes(document)
        except Exception as exc:
            QMessageBox.critical(self, "Open Failed", f"Could not open PDF:\n{exc}")
            return

        self.recent_files_repo.add(selected_path)
        self._settings.last_open_dir = str(Path(selected_path).parent)
        self.settings_repo.save(self._settings)
        self._refresh_welcome_recent_documents()

        if self.tab_widget.count() == 1 and self.tab_widget.tabText(0) == "Welcome":
            self.tab_widget.removeTab(0)

        canvas = PdfCanvas(self)
        canvas.set_display_mode(self._display_mode)
        canvas.set_night_mode(self._night_reading_mode)
        canvas.zoom_requested.connect(self._on_canvas_zoom_requested)
        canvas.zoom_level_changed.connect(self._on_canvas_zoom_level_changed)
        canvas.current_page_changed.connect(self._on_canvas_page_changed)
        canvas.page_context_requested.connect(self._show_page_context_menu)
        canvas.set_page_count(page_count, page_sizes=page_sizes)

        tab_name = Path(selected_path).name
        tab_index = self.tab_widget.addTab(canvas, tab_name)
        self._install_document_tab_close_button(tab_index, canvas)
        session = DocumentSession(
            path=selected_path,
            document=document,
            canvas=canvas,
            page_count=page_count,
            page_sizes=page_sizes,
            thumbnail_queue=list(range(page_count)),
        )
        self._sessions_by_tab_index[tab_index] = session

        # Avoid page-sync churn while lazy rendering warms up the first visible pages.
        self._suspend_canvas_page_sync = page_count > 0

        self.tab_widget.setCurrentIndex(tab_index)
        self._rebuild_session_index()
        self._load_thumbnails_for_current_session()
        self._load_toc_for_current_session()
        self._queue_render_for_current_session(center_page=0)

        if page_count > 0:
            self._set_thumbnail_selection(0)
            self._sync_page_controls(page_count=session.page_count, current_page=0)
            self._sync_zoom_label(session.canvas.zoom_level)

        if page_count == 0:
            self._resume_canvas_page_sync()

        self.statusBar().showMessage(f"Opened {tab_name} ({page_count} pages)")

    def _refresh_welcome_recent_documents(self) -> None:
        self.welcome_list.clear()
        recent_items = self.recent_files_repo.load()[:5]
        if not recent_items:
            empty = QListWidgetItem("No recent documents")
            empty.setFlags(empty.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.welcome_list.addItem(empty)
            return

        pdf_icon = self._icon("pdf_file")
        for recent_path in recent_items:
            item_path = str(Path(recent_path).resolve())
            item = QListWidgetItem(pdf_icon, f"{Path(item_path).name}\n{item_path}")
            item.setData(Qt.ItemDataRole.UserRole, item_path)
            item.setToolTip(item_path)
            self.welcome_list.addItem(item)

    def _clear_recent_history(self) -> None:
        self.recent_files_repo.clear()
        self._refresh_welcome_recent_documents()
        self.statusBar().showMessage("Recent history cleared")

    def _show_search_bar(self) -> None:
        session = self._current_session()
        if session is None:
            self.statusBar().showMessage("Open a document to search")
            return

        self.search_bar.setVisible(True)
        self._sync_search_ui(session)
        self.search_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search_input.selectAll()

    def _hide_search_bar(self) -> None:
        self._search_debounce_timer.stop()
        self._cancel_search_scan()
        session = self._current_session()
        if session is not None:
            self._clear_session_search(session)
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self.search_bar.setVisible(False)

    def _on_search_text_changed(self, text: str) -> None:
        session = self._current_session()
        if session is None:
            return

        session.search_query = text
        self._cancel_search_scan()
        session.search_matches.clear()
        session.active_search_match = -1
        session.canvas.set_search_highlights({}, None)
        if not text.strip():
            self._search_debounce_timer.stop()
            self._apply_search_state(session)
            return

        self.search_result_label.setText("Searching...")
        self.search_previous_button.setEnabled(False)
        self.search_next_button.setEnabled(False)
        self._set_search_no_results(False)
        self._search_debounce_timer.start()

    def _perform_search(self) -> None:
        session = self._current_session()
        if session is None:
            return

        query = session.search_query.strip()
        if not query:
            self._clear_session_search(session)
            return

        self._cancel_search_scan()
        session.search_matches.clear()
        session.active_search_match = -1
        session.canvas.set_search_highlights({}, None)
        self.search_previous_button.setEnabled(False)
        self.search_next_button.setEnabled(False)
        self._set_search_no_results(False)
        self._search_scan_session = session
        self._search_scan_query = query
        self._search_scan_page = 0
        self.search_result_label.setText(f"Searching 0 / {session.page_count}")
        self._search_scan_timer.start()

    def _process_search_page(self) -> None:
        session = self._search_scan_session
        if (
            session is None
            or session is not self._current_session()
            or session.search_query.strip() != self._search_scan_query
        ):
            self._cancel_search_scan()
            return

        if self._search_scan_page >= session.page_count:
            self._search_scan_timer.stop()
            session.active_search_match = self._first_match_index_for_page(
                session.search_matches,
                session.current_page,
            )
            self._search_scan_session = None
            self._apply_search_state(session, focus_active=bool(session.search_matches))
            return

        try:
            session.search_matches.extend(
                self.viewer_service.search_page(
                    session.document,
                    self._search_scan_page,
                    self._search_scan_query,
                )
            )
        except Exception as exc:
            self._cancel_search_scan()
            session.search_matches.clear()
            session.active_search_match = -1
            self._apply_search_state(session)
            QMessageBox.critical(self, "Search Failed", f"Could not search this PDF:\n{exc}")
            return

        self._search_scan_page += 1
        self.search_result_label.setText(
            f"Searching {self._search_scan_page} / {session.page_count}"
        )

    def _cancel_search_scan(self) -> None:
        self._search_scan_timer.stop()
        self._search_scan_session = None
        self._search_scan_query = ""
        self._search_scan_page = 0

    @staticmethod
    def _first_match_index_for_page(matches: list[SearchMatch], page_index: int) -> int:
        for match_index, match in enumerate(matches):
            if match.page_index >= page_index:
                return match_index
        return 0 if matches else -1

    def _go_previous_search_match(self) -> None:
        self._navigate_search_matches(-1)

    def _go_next_search_match(self) -> None:
        self._navigate_search_matches(1)

    def _navigate_search_matches(self, direction: int) -> None:
        session = self._current_session()
        if session is None:
            return
        if not session.search_matches:
            if session.search_query.strip():
                self._perform_search()
            return

        session.active_search_match = (
            session.active_search_match + direction
        ) % len(session.search_matches)
        self._apply_search_state(session, focus_active=True)

    def _apply_search_state(self, session: DocumentSession, focus_active: bool = False) -> None:
        highlights: dict[int, list[tuple[float, float, float, float]]] = {}
        for match in session.search_matches:
            highlights.setdefault(match.page_index, []).append(match.rect)

        active_match = None
        if 0 <= session.active_search_match < len(session.search_matches):
            match = session.search_matches[session.active_search_match]
            active_match = (match.page_index, match.rect)

        session.canvas.set_search_highlights(highlights, active_match)
        match_count = len(session.search_matches)
        has_matches = match_count > 0
        current_number = session.active_search_match + 1 if has_matches else 0
        self.search_result_label.setText(f"{current_number} / {match_count}")
        self.search_previous_button.setEnabled(has_matches)
        self.search_next_button.setEnabled(has_matches)
        self._set_search_no_results(bool(session.search_query.strip()) and not has_matches)

        if focus_active and active_match is not None:
            page_index, rect = active_match
            self._render_current_page(page_index, scroll_to_page=False)
            session.canvas.focus_search_match(page_index, rect)
            self.statusBar().showMessage(
                f'Found "{session.search_query.strip()}" | Match {current_number} of {match_count} | Page {page_index + 1}'
            )
        elif session.search_query.strip() and not has_matches:
            self.statusBar().showMessage(f'No matches for "{session.search_query.strip()}"')

    def _set_search_no_results(self, no_results: bool) -> None:
        self.search_input.setProperty("noResults", no_results)
        self.search_input.style().unpolish(self.search_input)
        self.search_input.style().polish(self.search_input)

    def _clear_session_search(self, session: DocumentSession) -> None:
        session.search_query = ""
        session.search_matches.clear()
        session.active_search_match = -1
        self._apply_search_state(session)

    def _restart_search_after_document_change(self, session: DocumentSession) -> None:
        if not session.search_query.strip():
            return
        self._cancel_search_scan()
        session.search_matches.clear()
        session.active_search_match = -1
        session.canvas.set_search_highlights({}, None)
        self._perform_search()

    def _sync_search_ui(self, session: DocumentSession | None) -> None:
        self.search_input.blockSignals(True)
        self.search_input.setText(session.search_query if session is not None else "")
        self.search_input.blockSignals(False)
        if session is None:
            self.search_result_label.setText("0 / 0")
            self.search_previous_button.setEnabled(False)
            self.search_next_button.setEnabled(False)
            self._set_search_no_results(False)
            return
        self._apply_search_state(session)

    def _open_recent_item(self, item: QListWidgetItem) -> None:
        item_path = item.data(Qt.ItemDataRole.UserRole)
        if not item_path:
            return

        path = Path(str(item_path))
        if not path.exists():
            QMessageBox.warning(
                self,
                "Recent File Missing",
                f"This document is no longer available:\n{path}",
            )
            self.recent_files_repo.remove(str(path))
            self._refresh_welcome_recent_documents()
            return

        self._open_document_by_path(str(path))

    def _save_current_document(self) -> None:
        session = self._current_session()
        if session is None:
            self.statusBar().showMessage("No document to save")
            return

        self._save_session(session)

    def _save_session(self, session: DocumentSession) -> bool:
        try:
            saved_path = self.document_service.save(
                document=session.document,
                current_path=session.path,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Save Failed", f"Could not save PDF:\n{exc}")
            return False

        session.path = saved_path
        session.command_history.mark_clean()
        self._set_session_dirty(session, False)
        self.recent_files_repo.add(saved_path)
        self._settings.last_open_dir = str(Path(saved_path).parent)
        self.settings_repo.save(self._settings)
        self.statusBar().showMessage(f"Saved {Path(saved_path).name}")
        return True

    def _save_current_document_as(self) -> None:
        session = self._current_session()
        if session is None:
            self.statusBar().showMessage("No document to save")
            return

        current_path = Path(session.path)
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF As",
            str(current_path.parent / current_path.name),
            "PDF files (*.pdf)",
        )
        if not selected:
            return

        target = Path(selected)
        if target.suffix.lower() != ".pdf":
            target = target.with_suffix(".pdf")

        if target.exists():
            answer = QMessageBox.question(
                self,
                "Overwrite File",
                f"{target.name} already exists.\nDo you want to overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                self.statusBar().showMessage("Save As cancelled")
                return

        try:
            saved_path = self.document_service.save(
                document=session.document,
                current_path=session.path,
                target_path=str(target),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Save As Failed", f"Could not save PDF:\n{exc}")
            return

        session.path = saved_path
        session.command_history.mark_clean()
        self._set_session_dirty(session, False)
        tab_index = self.tab_widget.currentIndex()
        if tab_index >= 0:
            self.tab_widget.setTabText(tab_index, Path(saved_path).name)
        self.recent_files_repo.add(saved_path)
        self._settings.last_open_dir = str(Path(saved_path).parent)
        self.settings_repo.save(self._settings)
        self.statusBar().showMessage(f"Saved as {Path(saved_path).name}")

    def _show_about(self) -> None:
        repo_url = self.REPOSITORY_URL
        if not repo_url:
            try:
                output = subprocess.check_output(
                    ["git", "config", "--get", "remote.origin.url"],
                    cwd=str(Path(__file__).resolve().parents[2]),
                    text=True,
                ).strip()
                if output:
                    repo_url = output
            except Exception:
                repo_url = ""
        if not repo_url:
            repo_url = "Repository URL not configured"

        dialog = QDialog(self)
        dialog.setWindowTitle("About Easy PDF Tool Kit")
        dialog.setMinimumWidth(560)
        dialog.setModal(True)

        root = QVBoxLayout(dialog)
        root.setContentsMargins(20, 18, 20, 16)
        root.setSpacing(14)

        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        app_icon_label = QLabel(dialog)
        app_icon_label.setPixmap(self._icon("tool_logo").pixmap(52, 52))
        app_icon_label.setFixedSize(52, 52)
        header_row.addWidget(app_icon_label)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title_label = QLabel("Easy PDF Tool Kit", dialog)
        title_label.setStyleSheet("font-size: 15pt; font-weight: 700;")
        subtitle_label = QLabel("Desktop-first offline PDF toolkit", dialog)
        subtitle_label.setStyleSheet(f"color: {self._theme.text_secondary}; font-size: 10.5pt;")
        title_col.addWidget(title_label)
        title_col.addWidget(subtitle_label)
        header_row.addLayout(title_col, 1)
        root.addLayout(header_row)

        info_card = QFrame(dialog)
        info_card.setStyleSheet(
            f"QFrame {{ background: {self._theme.bg_elevated}; border: 1px solid {self._theme.border}; border-radius: 10px; }}"
        )
        info_layout = QVBoxLayout(info_card)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(10)

        def add_info_row(icon_name: str, label: str, value: str) -> None:
            row = QHBoxLayout()
            row.setSpacing(8)
            icon_label = QLabel(info_card)
            icon_label.setPixmap(self._icon(icon_name).pixmap(16, 16))
            icon_label.setFixedSize(16, 16)
            key_label = QLabel(label, info_card)
            key_label.setStyleSheet(f"font-weight: 600; color: {self._theme.text_secondary};")
            value_label = QLabel(value, info_card)
            value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            row.addWidget(icon_label)
            row.addWidget(key_label)
            row.addWidget(value_label, 1)
            info_layout.addLayout(row)

        add_info_row("developer", "Developer", "Chetankumar Akarte")
        add_info_row("version", "Version", self.APP_VERSION)
        add_info_row("version", "Python", sys.version.split()[0])
        try:
            from PySide6 import __version__ as pyside_version
        except Exception:
            pyside_version = "unknown"
        try:
            import fitz

            pymupdf_version = getattr(fitz, "VersionBind", "unknown")
        except Exception:
            pymupdf_version = "unknown"
        add_info_row("version", "PySide6", pyside_version)
        add_info_row("version", "PyMuPDF", str(pymupdf_version))
        add_info_row("version", "Platform", sys.platform)

        repo_row = QHBoxLayout()
        repo_row.setSpacing(8)
        repo_icon = QLabel(info_card)
        repo_icon.setPixmap(self._icon("repo_link").pixmap(16, 16))
        repo_icon.setFixedSize(16, 16)
        repo_key = QLabel("Repository", info_card)
        repo_key.setStyleSheet(f"font-weight: 600; color: {self._theme.text_secondary};")
        if repo_url.startswith("http"):
            repo_link = QLabel(f"<a href='{repo_url}'>{repo_url}</a>", info_card)
            repo_link.setOpenExternalLinks(True)
            repo_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        else:
            repo_link = QLabel(repo_url, info_card)
            repo_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        repo_row.addWidget(repo_icon)
        repo_row.addWidget(repo_key)
        repo_row.addWidget(repo_link, 1)
        info_layout.addLayout(repo_row)

        useful_info = QLabel(
            "Useful info: fully offline processing, TOC/bookmarks panel, fit-width mode, continuous/single-page modes, and dark/light theme support.",
            info_card,
        )
        useful_info.setWordWrap(True)
        useful_info.setStyleSheet(f"color: {self._theme.text_secondary};")
        info_layout.addWidget(useful_info)

        root.addWidget(info_card)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        repo_button = QPushButton("Open Repository", dialog)
        repo_button.setIcon(self._icon("repo_link"))
        repo_button.setEnabled(repo_url.startswith("http"))
        repo_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(repo_url)))

        close_button = QPushButton("Close", dialog)
        close_button.setIcon(self._icon("about_info"))
        close_button.clicked.connect(dialog.accept)

        button_style = (
            f"QPushButton {{"
            f"background: {self._theme.bg_panel};"
            f"border: 1px solid {self._theme.border};"
            f"border-radius: 8px;"
            f"padding: 7px 14px;"
            f"color: {self._theme.text_primary};"
            f"}}"
            f"QPushButton:hover {{"
            f"background: {self._theme.bg_elevated};"
            f"border-color: {self._theme.accent};"
            f"}}"
            f"QPushButton:focus {{"
            f"border: 2px solid {self._theme.accent};"
            f"}}"
        )
        repo_button.setStyleSheet(button_style)
        close_button.setStyleSheet(button_style)

        buttons.addWidget(repo_button)
        buttons.addWidget(close_button)
        root.addLayout(buttons)

        dialog.exec()

    def _rotate_current_page_left(self) -> None:
        session = self._current_session()
        if session is None:
            return
        self._rotate_page(session.current_page, -90)

    def _rotate_current_page_right(self) -> None:
        session = self._current_session()
        if session is None:
            return
        self._rotate_page(session.current_page, 90)

    def _delete_current_page(self) -> None:
        session = self._current_session()
        if session is None:
            return
        self._delete_page(session.current_page)

    def _open_insert_blank_page_dialog(self, *, reference_page: int | None = None) -> None:
        session = self._current_session()
        if session is None or session.page_count <= 0:
            self.statusBar().showMessage("No document loaded")
            return

        if reference_page is None:
            self.page_spin.interpretText()
            page_index = self.page_spin.value() - 1
            session.current_page = page_index
        else:
            page_index = reference_page
        page_index = max(0, min(page_index, session.page_count - 1))
        dialog = InsertBlankPageDialog(
            current_page=page_index,
            page_count=session.page_count,
            current_page_size=session.page_sizes[page_index],
            theme=self._theme,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        request = dialog.build_request()
        try:
            command = InsertBlankPagesCommand(
                self.page_service,
                session.document,
                request.insertion_index,
                request.width,
                request.height,
                request.count,
            )
            session.command_history.execute(command)
        except Exception as exc:
            QMessageBox.critical(self, "Insert Blank Pages Failed", f"Could not insert pages:\n{exc}")
            return

        self._refresh_after_page_command(session, request.insertion_index)
        page_word = "page" if request.count == 1 else "pages"
        self.statusBar().showMessage(
            f"Inserted {request.count} blank {page_word} at page {request.insertion_index + 1}"
        )

    def _open_split_extract_dialog(self) -> None:
        session = self._current_session()
        if session is None:
            self.statusBar().showMessage("No document loaded")
            return

        dialog = SplitExtractDialog(
            source_path=session.path,
            current_page=session.current_page,
            page_count=session.page_count,
            theme=self._theme,
            parent=self,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        request = dialog.build_request()

        try:
            if request.mode == SplitExtractDialog.MODE_CURRENT:
                self._run_extract_current_page(session, request.save_to_current_location)
            elif request.mode == SplitExtractDialog.MODE_RANGE:
                self._run_extract_page_range(
                    session,
                    request.page_range_text,
                    request.save_to_current_location,
                )
            else:
                self._run_split_by_range(
                    session,
                    request.split_size,
                    request.split_file_name_template,
                    request.save_to_current_location,
                )
        except Exception as exc:
            QMessageBox.critical(self, "Split / Extract Failed", f"Could not complete operation:\n{exc}")

    def _extract_images_from_document(self) -> None:
        session = self._current_session()
        if session is None:
            self.statusBar().showMessage("No document loaded")
            return

        output_directory = QFileDialog.getExistingDirectory(
            self,
            "Select Folder for Extracted Images",
            str(Path(session.path).parent),
        )
        if not output_directory:
            return

        try:
            extracted = self.pdf_adapter.extract_images(
                session.document,
                output_directory,
                Path(session.path).stem,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Image Extraction Failed", f"Could not extract images:\n{exc}")
            return

        if not extracted:
            QMessageBox.information(self, "Extract Images", "No embedded images were found in this PDF.")
            self.statusBar().showMessage("No embedded images found")
            return

        QMessageBox.information(
            self,
            "Extract Images",
            f"Extracted {len(extracted)} image(s) to:\n{output_directory}",
        )
        self.statusBar().showMessage(f"Extracted {len(extracted)} image(s)")

    def _show_page_context_menu(
        self,
        page_index: int,
        x_ratio: float,
        y_ratio: float,
        global_position,
    ) -> None:
        session = self._current_session()
        if session is None:
            return

        image_match = self.pdf_adapter.image_at_point(
            session.document,
            page_index,
            x_ratio,
            y_ratio,
        )
        if image_match is None:
            return

        xref, extension = image_match
        menu = QMenu(self)
        extract_action = menu.addAction(self._icon("extract_image"), "Extract This Image...")
        if menu.exec(global_position) != extract_action:
            return

        suggested_name = f"{Path(session.path).stem}_page_{page_index + 1}_image.{extension}"
        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Extract Image",
            str(Path(session.path).parent / suggested_name),
            f"{extension.upper()} image (*.{extension});;All files (*)",
        )
        if not selected:
            return

        destination = Path(selected)
        if not destination.suffix:
            destination = destination.with_suffix(f".{extension}")

        try:
            self.pdf_adapter.extract_image(session.document, xref, str(destination))
        except Exception as exc:
            QMessageBox.critical(self, "Image Extraction Failed", f"Could not extract image:\n{exc}")
            return

        self.statusBar().showMessage(f"Extracted image to {destination.name}")

    def _run_extract_current_page(self, session: DocumentSession, save_to_current: bool) -> None:
        page_number = session.current_page + 1
        suggested_name = f"{Path(session.path).stem}_page_{page_number}.pdf"
        destination = self._resolve_single_extract_destination(session, suggested_name, save_to_current)
        if destination is None:
            return

        if destination.exists() and not self._confirm_overwrite_paths([destination]):
            return

        self.page_service.extract_pages(session.document, [session.current_page], str(destination))
        self.statusBar().showMessage(f"Extracted current page to {destination.name}")

    def _run_extract_page_range(self, session: DocumentSession, page_range_text: str, save_to_current: bool) -> None:
        page_indices = self.page_service.parse_page_ranges(page_range_text, session.page_count)
        compact = page_range_text.replace(" ", "").replace(",", "_").replace("-", "to")
        suggested_name = f"{Path(session.path).stem}_extract_{compact}.pdf"
        destination = self._resolve_single_extract_destination(session, suggested_name, save_to_current)
        if destination is None:
            return

        if destination.exists() and not self._confirm_overwrite_paths([destination]):
            return

        self.page_service.extract_pages(session.document, page_indices, str(destination))
        self.statusBar().showMessage(f"Extracted {len(page_indices)} pages to {destination.name}")

    def _run_split_by_range(
        self,
        session: DocumentSession,
        split_size: int,
        template: str,
        save_to_current: bool,
    ) -> None:
        if split_size <= 0:
            raise ValueError("Split range must be greater than zero.")

        output_dir = self._resolve_split_output_directory(session, save_to_current)
        if output_dir is None:
            return

        output_paths: list[Path] = []
        chunk_ranges: list[tuple[int, int]] = []
        part_index = 1
        for start in range(0, session.page_count, split_size):
            end = min(start + split_size - 1, session.page_count - 1)
            file_name = self._build_split_filename(
                source_path=Path(session.path),
                split_size=split_size,
                part_index=part_index,
                start_page=start + 1,
                end_page=end + 1,
                template=template,
            )
            output_paths.append(output_dir / file_name)
            chunk_ranges.append((start, end))
            part_index += 1

        existing = [path for path in output_paths if path.exists()]
        if existing and not self._confirm_overwrite_paths(existing):
            return

        created: list[Path] = []
        for idx, (start, end) in enumerate(chunk_ranges):
            page_indices = list(range(start, end + 1))
            self.page_service.extract_pages(session.document, page_indices, str(output_paths[idx]))
            created.append(output_paths[idx])

        self.statusBar().showMessage(f"Split complete: {len(created)} files created in {output_dir}")

    def _resolve_single_extract_destination(
        self,
        session: DocumentSession,
        suggested_name: str,
        save_to_current: bool,
    ) -> Path | None:
        current_path = Path(session.path)
        if save_to_current:
            return current_path.parent / suggested_name

        selected, _ = QFileDialog.getSaveFileName(
            self,
            "Extract PDF",
            str(current_path.parent / suggested_name),
            "PDF files (*.pdf)",
        )
        if not selected:
            return None

        destination = Path(selected)
        if destination.suffix.lower() != ".pdf":
            destination = destination.with_suffix(".pdf")
        return destination

    def _resolve_split_output_directory(self, session: DocumentSession, save_to_current: bool) -> Path | None:
        current_path = Path(session.path)
        if save_to_current:
            return current_path.parent

        selected = QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder for Split Files",
            str(current_path.parent),
        )
        if not selected:
            return None
        return Path(selected)

    def _build_split_filename(
        self,
        source_path: Path,
        split_size: int,
        part_index: int,
        start_page: int,
        end_page: int,
        template: str,
    ) -> str:
        return self._page_service.build_split_filename(
            source_stem=source_path.stem,
            split_size=split_size,
            part_index=part_index,
            start_page=start_page,
            end_page=end_page,
            template=template,
        )

    def _confirm_overwrite_paths(self, paths: list[Path]) -> bool:
        if not paths:
            return True

        if len(paths) == 1:
            message = f"{paths[0].name} already exists.\nDo you want to overwrite it?"
        else:
            message = (
                f"{len(paths)} output files already exist in destination.\n"
                "Do you want to overwrite them?"
            )

        answer = QMessageBox.question(
            self,
            "Overwrite Existing Files",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _close_current_document(self) -> None:
        session = self._current_session()
        if session is None:
            self.statusBar().showMessage("No document to close")
            return

        tab_index = self.tab_widget.currentIndex()
        if tab_index < 0:
            self.statusBar().showMessage("No document to close")
            return

        if self._close_tab(tab_index):
            self.statusBar().showMessage("Document closed")

    def _install_document_tab_close_button(self, tab_index: int, document_widget: QWidget) -> None:
        close_button = QToolButton(self.tab_widget.tabBar())
        close_button.setObjectName("documentTabCloseButton")
        close_button.setIcon(self._icon("close_file"))
        close_button.setIconSize(QSize(16, 16))
        close_button.setFixedSize(22, 22)
        close_button.setToolTip("Close document")
        close_button.setAccessibleName("Close document")
        close_button.clicked.connect(
            lambda: self._close_document_widget(document_widget)
        )
        self.tab_widget.tabBar().setTabButton(
            tab_index,
            QTabBar.ButtonPosition.RightSide,
            close_button,
        )

    def _close_document_widget(self, document_widget: QWidget) -> None:
        tab_index = self.tab_widget.indexOf(document_widget)
        if tab_index >= 0:
            self._close_tab(tab_index)

    def _exit_application(self) -> None:
        self.close()

    def _zoom_in(self) -> None:
        session = self._current_session()
        if session is None:
            self.statusBar().showMessage("No document loaded")
            return

        self._fit_mode = self.FIT_MODE_MANUAL
        session.canvas.zoom_in()
        self.statusBar().showMessage(f"Zoom: {int(session.canvas.zoom_level * 100)}%")
        self._sync_zoom_label(session.canvas.zoom_level)

    def _fit_width(self) -> None:
        self._apply_fit_width(update_status=True, align_top=False)

    def _apply_fit_width(self, update_status: bool, align_top: bool) -> None:
        session = self._current_session()
        if session is None:
            if update_status:
                self.statusBar().showMessage("No document loaded")
            return

        self._fit_mode = self.FIT_MODE_WIDTH
        session.canvas.fit_current_page_to_width()
        if align_top:
            session.canvas.scroll_to_page(session.current_page)
        if update_status:
            self.statusBar().showMessage("Zoom: Fit width")
        self._sync_zoom_label(session.canvas.zoom_level)

    def _zoom_out(self) -> None:
        session = self._current_session()
        if session is None:
            self.statusBar().showMessage("No document loaded")
            return

        self._fit_mode = self.FIT_MODE_MANUAL
        session.canvas.zoom_out()
        self.statusBar().showMessage(f"Zoom: {int(session.canvas.zoom_level * 100)}%")
        self._sync_zoom_label(session.canvas.zoom_level)

    def _reset_zoom(self) -> None:
        session = self._current_session()
        if session is None:
            self.statusBar().showMessage("No document loaded")
            return

        self._fit_mode = self.FIT_MODE_MANUAL
        session.canvas.set_zoom_level(1.0)
        self.statusBar().showMessage("Zoom: 100%")
        self._sync_zoom_label(session.canvas.zoom_level)

    def _set_reader_display_mode(self, mode: str) -> None:
        self._display_mode = mode
        self._sync_reader_mode_ui()
        session = self._current_session()
        if session is None:
            return

        session.canvas.set_display_mode(mode)
        session.canvas.scroll_to_page(session.current_page)

    def _toggle_reader_display_mode(self) -> None:
        next_mode = self.DISPLAY_MODE_SINGLE if self._display_mode == self.DISPLAY_MODE_CONTINUOUS else self.DISPLAY_MODE_CONTINUOUS
        self._set_reader_display_mode(next_mode)

    def _sync_reader_mode_ui(self) -> None:
        is_continuous = self._display_mode == self.DISPLAY_MODE_CONTINUOUS
        if is_continuous:
            self.view_continuous_action.setText("Continuous")
            self.view_single_page_action.setText("Single Page")
            self.view_continuous_action.setIcon(self._icon("continuous_mode_checked"))
            self.view_single_page_action.setIcon(self._icon("single_page_mode"))
        else:
            self.view_continuous_action.setText("Continuous")
            self.view_single_page_action.setText("Single Page")
            self.view_continuous_action.setIcon(self._icon("continuous_mode"))
            self.view_single_page_action.setIcon(self._icon("single_page_mode_checked"))

        if is_continuous:
            self.toggle_display_mode_action.setIcon(self._icon("continuous_mode"))
            self.toggle_display_mode_action.setToolTip("Switch to Single Page mode")
        else:
            self.toggle_display_mode_action.setIcon(self._icon("single_page_mode"))
            self.toggle_display_mode_action.setToolTip("Switch to Continuous mode")

    def _close_tab(self, index: int) -> bool:
        session = self._sessions_by_tab_index.get(index)
        if session is not None and not self._confirm_close_session(session):
            return False

        session = self._sessions_by_tab_index.pop(index, None)
        if session is not None:
            if session is self._search_scan_session:
                self._cancel_search_scan()
            self.pdf_adapter.close_document(session.document)

        self.tab_widget.removeTab(index)
        self._rebuild_session_index()

        if self.tab_widget.count() == 0:
            self._search_debounce_timer.stop()
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)
            self.search_bar.setVisible(False)
            self._refresh_welcome_recent_documents()
            self.tab_widget.addTab(self.welcome_list, "Welcome")
            self.thumbnail_list.clear()
            self.thumbnail_list.addItem("No document loaded")
            self.toc_tree.clear()
            self.toc_tree.setVisible(False)
            self.toggle_toc_action.blockSignals(True)
            self.toggle_toc_action.setChecked(False)
            self.toggle_toc_action.blockSignals(False)
            self._sync_page_controls(page_count=0, current_page=0)
            self._sync_zoom_label(1.0)

        current_session = self._current_session()
        self._sync_document_actions(page_count=current_session.page_count if current_session is not None else 0)
        return True

    def _confirm_close_session(self, session: DocumentSession) -> bool:
        if not session.is_dirty:
            return True

        answer = QMessageBox.warning(
            self,
            "Unsaved Changes",
            f"Save changes to {Path(session.path).name} before closing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            return self._save_session(session)
        return True

    def _on_tab_changed(self, _index: int) -> None:
        self._search_debounce_timer.stop()
        self._cancel_search_scan()
        self._load_thumbnails_for_current_session()
        self._load_toc_for_current_session()
        session = self._current_session()
        if session is not None:
            session.canvas.set_display_mode(self._display_mode)
            session.canvas.set_night_mode(self._night_reading_mode)
            self._queue_render_for_current_session(center_page=session.current_page)
            self._sync_document_actions(page_count=session.page_count)
        else:
            self._sync_document_actions(page_count=0)
        self._sync_search_ui(session)
        self._sync_undo_redo_actions(session)

    def _on_thumbnail_selected(self, page_index: int) -> None:
        if page_index < 0:
            return
        self._render_current_page(page_index)

    def _on_canvas_page_changed(self, page_index: int) -> None:
        if self._suspend_canvas_page_sync:
            return

        session = self._current_session()
        if session is None:
            return

        if session.current_page == page_index:
            return

        session.current_page = page_index
        self._set_thumbnail_selection(page_index)
        self._sync_page_controls(page_count=session.page_count, current_page=page_index)
        self._sync_zoom_label(session.canvas.zoom_level)
        self.statusBar().showMessage(
            f"{Path(session.path).name} | Page {page_index + 1}/{session.page_count} | Zoom: {int(session.canvas.zoom_level * 100)}%"
        )
        self._queue_render_for_current_session(center_page=page_index)

    def _on_canvas_zoom_level_changed(self, _zoom_level: float) -> None:
        session = self._current_session()
        if session is None:
            return

        cached_pages = list(session.page_cache.keys())
        session.page_cache.clear()
        session.render_queue.clear()

        for page_index in cached_pages:
            session.canvas.clear_page_image(page_index)

        self._queue_render_for_current_session(center_page=session.current_page)

    def _on_page_spin_changed(self, one_based_page: int) -> None:
        if not self.page_spin.isEnabled():
            return
        self._render_current_page(one_based_page - 1)

    def _go_previous_page(self) -> None:
        session = self._current_session()
        if session is None:
            return
        self._render_current_page(max(session.current_page - 1, 0))

    def _go_first_page(self) -> None:
        session = self._current_session()
        if session is None:
            return
        self._render_current_page(0)

    def _go_next_page(self) -> None:
        session = self._current_session()
        if session is None:
            return
        self._render_current_page(min(session.current_page + 1, session.page_count - 1))

    def _go_last_page(self) -> None:
        session = self._current_session()
        if session is None:
            return
        self._render_current_page(session.page_count - 1)

    def _bind_navigation_shortcuts(self) -> None:
        self._shortcut_prev_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        self._shortcut_prev_left.activated.connect(self._go_previous_page)

        self._shortcut_next_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        self._shortcut_next_right.activated.connect(self._go_next_page)

        self._shortcut_prev_pageup = QShortcut(QKeySequence(Qt.Key.Key_PageUp), self)
        self._shortcut_prev_pageup.activated.connect(self._go_previous_page)

        self._shortcut_next_pagedown = QShortcut(QKeySequence(Qt.Key.Key_PageDown), self)
        self._shortcut_next_pagedown.activated.connect(self._go_next_page)

    def _current_session(self) -> DocumentSession | None:
        if not hasattr(self, "tab_widget"):
            return None
        current_index = self.tab_widget.currentIndex()
        return self._sessions_by_tab_index.get(current_index)

    def _load_thumbnails_for_current_session(self) -> None:
        session = self._current_session()
        self.thumbnail_list.clear()
        if session is None:
            self._thumbnail_progress_timer.stop()
            self.thumbnail_list.addItem("No document loaded")
            self._sync_page_controls(page_count=0, current_page=0)
            return

        progress_icon = self._thumbnail_progress_icon()
        for page_index in range(session.page_count):
            is_loading = page_index not in session.thumbnail_cache
            icon = session.thumbnail_cache.get(page_index, progress_icon)
            item = QListWidgetItem(icon, f"Page {page_index + 1}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setData(Qt.ItemDataRole.UserRole, page_index)
            item.setData(self.THUMBNAIL_LOADING_ROLE, is_loading)
            self.thumbnail_list.addItem(item)

        self._set_thumbnail_selection(session.current_page)
        self._sync_page_controls(page_count=session.page_count, current_page=session.current_page)
        self._sync_thumbnail_progress_timer(session)

    def _thumbnail_progress_icon(self) -> QIcon:
        pixmap = QPixmap(self.THUMBNAIL_WIDTH, self.THUMBNAIL_HEIGHT)
        pixmap.fill(QColor(self._theme.bg_elevated))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(self._theme.border), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        spinner_rect = QRectF(
            (self.THUMBNAIL_WIDTH - 34) / 2,
            (self.THUMBNAIL_HEIGHT - 34) / 2,
            34,
            34,
        )
        painter.drawArc(spinner_rect, 0, 360 * 16)
        painter.setPen(QPen(QColor(self._theme.accent), 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(spinner_rect, self._thumbnail_progress_angle * 16, 105 * 16)
        painter.end()
        return QIcon(pixmap)

    def _animate_thumbnail_progress(self) -> None:
        session = self._current_session()
        if session is None or self.thumbnail_list.count() != session.page_count:
            self._thumbnail_progress_timer.stop()
            return

        self._thumbnail_progress_angle = (self._thumbnail_progress_angle - 24) % 360
        progress_icon = self._thumbnail_progress_icon()
        has_pending = False
        for page_index in range(session.page_count):
            item = self.thumbnail_list.item(page_index)
            if item is None or not item.data(self.THUMBNAIL_LOADING_ROLE):
                continue
            has_pending = True
            if self.thumbnail_list.viewport().rect().intersects(
                self.thumbnail_list.visualItemRect(item)
            ):
                item.setIcon(progress_icon)

        if not has_pending:
            self._thumbnail_progress_timer.stop()

    def _sync_thumbnail_progress_timer(self, session: DocumentSession) -> None:
        has_pending = any(
            item is not None and bool(item.data(self.THUMBNAIL_LOADING_ROLE))
            for item in (
                self.thumbnail_list.item(page_index)
                for page_index in range(session.page_count)
            )
        )
        if has_pending:
            queued = set(session.thumbnail_queue)
            session.thumbnail_queue.extend(
                page_index
                for page_index in range(session.page_count)
                if self.thumbnail_list.item(page_index).data(self.THUMBNAIL_LOADING_ROLE)
                and page_index not in session.thumbnail_cache
                and page_index not in queued
            )
            if not self._thumbnail_progress_timer.isActive():
                self._thumbnail_progress_timer.start()
            if not self._background_render_timer.isActive():
                self._background_render_timer.start()
        elif not has_pending:
            self._thumbnail_progress_timer.stop()

    def _render_current_page(self, page_index: int, scroll_to_page: bool = True) -> None:
        session = self._current_session()
        if session is None:
            return

        if page_index < 0 or page_index >= session.page_count:
            return

        session.current_page = page_index
        if scroll_to_page:
            session.canvas.scroll_to_page(page_index)
        self._set_thumbnail_selection(page_index)
        self._sync_page_controls(page_count=session.page_count, current_page=page_index)
        self._sync_zoom_label(session.canvas.zoom_level)
        self.statusBar().showMessage(
            f"{Path(session.path).name} | Page {page_index + 1}/{session.page_count} | Zoom: {int(session.canvas.zoom_level * 100)}%"
        )
        self._queue_render_for_current_session(center_page=page_index)

    def _set_thumbnail_selection(self, page_index: int) -> None:
        self.thumbnail_list.blockSignals(True)
        self.thumbnail_list.setCurrentRow(page_index)
        self.thumbnail_list.blockSignals(False)

    def _set_thumbnail_panel_visible(self, visible: bool) -> None:
        if not hasattr(self, "side_panel_tabs"):
            return

        self.side_panel_tabs.setTabVisible(self.thumbnail_tab_index, visible)
        if visible:
            self.side_panel_tabs.setCurrentIndex(self.thumbnail_tab_index)

        self._refresh_toc_toggle_ui(
            toc_visible=self.side_panel_tabs.isTabVisible(self.toc_tab_index),
            has_toc=self.toc_tree.topLevelItemCount() > 0,
        )
        self.side_panel_tabs.setVisible(
            self.side_panel_tabs.isTabVisible(self.thumbnail_tab_index)
            or self.side_panel_tabs.isTabVisible(self.toc_tab_index)
        )
        self._update_side_panel_sizes()

    def _set_toc_panel_visible(self, visible: bool) -> None:
        if not hasattr(self, "side_panel_tabs"):
            return

        has_toc = self.toc_tree.topLevelItemCount() > 0
        final_visible = visible and has_toc
        self.side_panel_tabs.setTabVisible(self.toc_tab_index, final_visible)
        if final_visible:
            self.side_panel_tabs.setCurrentIndex(self.toc_tab_index)

        any_visible = self.side_panel_tabs.isTabVisible(self.thumbnail_tab_index) or final_visible
        self.side_panel_tabs.setVisible(any_visible)
        self._refresh_toc_toggle_ui(final_visible, has_toc)
        self._update_side_panel_sizes()

    def _refresh_toc_toggle_ui(self, toc_visible: bool, has_toc: bool) -> None:
        if hasattr(self, "toc_edge_toggle_button"):
            self.toc_edge_toggle_button.setEnabled(has_toc)
            self.toc_edge_toggle_button.setToolTip("Close Bookmarks / TOC")

        if hasattr(self, "toc_toggle_button"):
            self.toc_toggle_button.setEnabled(has_toc)

    def _load_toc_for_current_session(self) -> None:
        self.toc_tree.clear()
        session = self._current_session()
        if session is None:
            self.toggle_toc_action.setEnabled(False)
            self._set_toc_panel_visible(False)
            return

        try:
            toc_entries = session.document.get_toc(simple=True)
        except Exception:
            toc_entries = []

        if not toc_entries:
            self.toggle_toc_action.setEnabled(False)
            self.toggle_toc_action.blockSignals(True)
            self.toggle_toc_action.setChecked(False)
            self.toggle_toc_action.blockSignals(False)
            self._set_toc_panel_visible(False)
            return

        stack: list[tuple[int, QTreeWidgetItem]] = []
        for level, title, page in toc_entries:
            page_index = max(0, int(page) - 1)
            item = QTreeWidgetItem([title or f"Page {page_index + 1}"])
            item.setData(0, Qt.ItemDataRole.UserRole, page_index)

            while stack and stack[-1][0] >= level:
                stack.pop()

            if stack:
                stack[-1][1].addChild(item)
            else:
                self.toc_tree.addTopLevelItem(item)

            stack.append((level, item))

        self.toc_tree.expandToDepth(0)
        self.toggle_toc_action.setEnabled(True)
        self._set_toc_panel_visible(self.toggle_toc_action.isChecked())

    def _on_toc_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        page_index = item.data(0, Qt.ItemDataRole.UserRole)
        if page_index is None:
            return
        self._render_current_page(int(page_index))

    def _sync_page_controls(self, page_count: int, current_page: int) -> None:
        if not hasattr(self, "page_spin"):
            return

        enabled = page_count > 0
        self.page_spin.blockSignals(True)
        self.page_spin.setEnabled(enabled)
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(max(page_count, 1))
        self.page_spin.setValue(max(min(current_page + 1, max(page_count, 1)), 1))
        self.page_spin.blockSignals(False)
        self.page_total_label.setText(f"/ {page_count}")
        self.first_page_button.setEnabled(enabled and current_page > 0)
        self.previous_page_button.setEnabled(enabled and current_page > 0)
        self.next_page_button.setEnabled(enabled and current_page < page_count - 1)
        self.last_page_button.setEnabled(enabled and current_page < page_count - 1)
        self._sync_document_actions(page_count=page_count)

    def _sync_zoom_label(self, zoom_level: float) -> None:
        self.zoom_label.setText(f"{int(zoom_level * 100)}%")

    def _on_canvas_zoom_requested(self, direction: int) -> None:
        if direction > 0:
            self._zoom_in()
        elif direction < 0:
            self._zoom_out()

    def _get_thumbnail_icon(self, session: DocumentSession, page_index: int) -> QIcon:
        cached_icon = session.thumbnail_cache.get(page_index)
        if cached_icon is not None:
            return cached_icon

        preview = session.page_cache.get(page_index)
        if preview is None:
            preview = self.pdf_adapter.render_page(
                session.document,
                page_index=page_index,
                zoom=0.22,
                invert_colors=self._night_reading_mode,
                dpr=1.0,
            )
        preview_pixmap = QPixmap.fromImage(preview).scaled(
            self.THUMBNAIL_WIDTH,
            self.THUMBNAIL_HEIGHT,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        icon = QIcon(preview_pixmap)
        session.thumbnail_cache[page_index] = icon

        if len(session.thumbnail_cache) > self.THUMBNAIL_CACHE_LIMIT:
            oldest_key = next(iter(session.thumbnail_cache))
            del session.thumbnail_cache[oldest_key]

        return icon

    def _queue_render_for_current_session(self, center_page: int) -> None:
        session = self._current_session()
        if session is None:
            return

        start = max(0, center_page - self.VIRTUAL_RENDER_RADIUS)
        end = min(session.page_count - 1, center_page + self.VIRTUAL_RENDER_RADIUS)
        desired_pages: list[int] = []
        for distance in range(self.VIRTUAL_RENDER_RADIUS + 1):
            candidates = (center_page,) if distance == 0 else (center_page - distance, center_page + distance)
            for page_index in candidates:
                if start <= page_index <= end:
                    desired_pages.append(page_index)

        session.render_queue = [
            page_index for page_index in desired_pages
            if page_index not in session.page_cache
        ]

        for page_index in desired_pages:
            if page_index not in session.page_cache or page_index in session.thumbnail_cache:
                continue
            self._set_generated_thumbnail(session, page_index, self._get_thumbnail_icon(session, page_index))

        if (session.render_queue or session.thumbnail_queue) and not self._background_render_timer.isActive():
            self._background_render_timer.start()

    def _evict_distant_page_cache(self, session: DocumentSession) -> None:
        if len(session.page_cache) <= self.PAGE_CACHE_LIMIT:
            return

        current = session.current_page
        protected_start = max(0, current - self.VIRTUAL_RENDER_RADIUS)
        protected_end = min(session.page_count - 1, current + self.VIRTUAL_RENDER_RADIUS)

        candidates = [
            page
            for page in session.page_cache
            if page < protected_start or page > protected_end
        ]
        candidates.sort(key=lambda page: abs(page - current), reverse=True)

        for page in candidates:
            if len(session.page_cache) <= self.PAGE_CACHE_LIMIT:
                break
            session.page_cache.pop(page, None)
            session.canvas.clear_page_image(page)

    def _process_background_render_step(self) -> None:
        session = self._current_session()
        if session is None:
            self._background_render_timer.stop()
            return

        if not session.render_queue:
            self._process_thumbnail_generation_step(session)
            return

        page_index = session.render_queue.pop(0)
        if page_index in session.page_cache:
            return

        try:
            page_image = self.pdf_adapter.render_page(
                session.document,
                page_index=page_index,
                zoom=session.canvas.zoom_level,
                invert_colors=self._night_reading_mode,
                dpr=session.canvas.devicePixelRatioF() or 1.0,
            )
        except Exception:
            return

        session.page_cache[page_index] = page_image
        session.canvas.set_page_image(page_index, page_image)
        self._evict_distant_page_cache(session)

        if not session.initial_fit_applied and page_index == session.current_page:
            self._fit_mode = self.FIT_MODE_WIDTH
            self._apply_fit_width(update_status=False, align_top=True)
            session.initial_fit_applied = True
            self._sync_zoom_label(session.canvas.zoom_level)

        if self._suspend_canvas_page_sync and page_index == session.current_page:
            self._resume_canvas_page_sync()

        if page_index not in session.thumbnail_cache:
            self._set_generated_thumbnail(session, page_index, self._get_thumbnail_icon(session, page_index))

    def _process_thumbnail_generation_step(self, session: DocumentSession) -> None:
        while session.thumbnail_queue and session.thumbnail_queue[0] in session.thumbnail_cache:
            session.thumbnail_queue.pop(0)

        if not session.thumbnail_queue:
            self._background_render_timer.stop()
            self._sync_thumbnail_progress_timer(session)
            return

        page_index = session.thumbnail_queue.pop(0)
        try:
            icon = self._get_thumbnail_icon(session, page_index)
        except Exception:
            return
        self._set_generated_thumbnail(session, page_index, icon)

    def _set_generated_thumbnail(self, session: DocumentSession, page_index: int, icon: QIcon) -> None:
        if session is not self._current_session() or self.thumbnail_list.count() != session.page_count:
            return
        item = self.thumbnail_list.item(page_index)
        if item is not None:
            item.setIcon(icon)
            item.setData(self.THUMBNAIL_LOADING_ROLE, False)
        self._sync_thumbnail_progress_timer(session)

    def _rebuild_session_index(self) -> None:
        rebuilt: dict[int, DocumentSession] = {}
        for index in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(index)
            for session in self._sessions_by_tab_index.values():
                if session.canvas is widget:
                    rebuilt[index] = session
                    break
        self._sessions_by_tab_index = rebuilt

    def _resume_canvas_page_sync(self) -> None:
        self._suspend_canvas_page_sync = False

    def _initial_open_directory(self) -> str:
        if self._settings.last_open_dir:
            path = Path(self._settings.last_open_dir)
            if path.exists() and path.is_dir():
                return str(path)
        return str(Path.home())

    def closeEvent(self, event):  # noqa: N802
        for session in list(self._sessions_by_tab_index.values()):
            if not self._confirm_close_session(session):
                event.ignore()
                return

        geometry = self.geometry()
        self._settings.window_x = geometry.x()
        self._settings.window_y = geometry.y()
        self._settings.window_width = geometry.width()
        self._settings.window_height = geometry.height()
        self.settings_repo.save(self._settings)
        super().closeEvent(event)

    def _show_thumbnail_context_menu(self, pos) -> None:
        item = self.thumbnail_list.itemAt(pos)
        if item is None:
            return
        page_index = self.thumbnail_list.row(item)
        if self._current_session() is None:
            return

        menu = QMenu(self)
        rotate_left_action = QAction(self._icon("rotate_left"), "Rotate Left (90° CCW)", menu)
        rotate_left_action.triggered.connect(lambda: self._rotate_page(page_index, -90))
        rotate_right_action = QAction(self._icon("rotate_right"), "Rotate Right (90° CW)", menu)
        rotate_right_action.triggered.connect(lambda: self._rotate_page(page_index, 90))
        insert_action = QAction(self._icon("insert_blank_page"), "Insert Blank Pages...", menu)
        insert_action.triggered.connect(
            lambda: self._open_insert_blank_page_dialog(reference_page=page_index)
        )
        delete_action = QAction(self._icon("delete_page"), "Delete Page", menu)
        delete_action.triggered.connect(lambda: self._delete_page(page_index))

        menu.addAction(rotate_left_action)
        menu.addAction(rotate_right_action)
        menu.addSeparator()
        menu.addAction(insert_action)
        menu.addAction(delete_action)
        menu.exec(self.thumbnail_list.mapToGlobal(pos))

    def _rotate_page(self, page_index: int, degrees: int) -> None:
        session = self._current_session()
        if session is None:
            return
        try:
            session.command_history.execute(
                RotatePageCommand(self.page_service, session.document, page_index, degrees)
            )
        except Exception as exc:
            QMessageBox.critical(self, "Rotate Failed", f"Could not rotate page:\n{exc}")
            return

        self._refresh_after_page_command(session, page_index)

        direction = "left" if degrees < 0 else "right"
        self.statusBar().showMessage(f"Page {page_index + 1} rotated {direction}")

    def _delete_page(self, page_index: int) -> None:
        session = self._current_session()
        if session is None:
            return
        if session.page_count <= 1:
            QMessageBox.warning(self, "Cannot Delete", "Cannot delete the only page in the document.")
            return

        answer = QMessageBox.question(
            self,
            "Delete Page",
            f"Delete page {page_index + 1} of {session.page_count}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            session.command_history.execute(
                DeletePageCommand(self.page_service, session.document, page_index)
            )
        except Exception as exc:
            QMessageBox.critical(self, "Delete Failed", f"Could not delete page:\n{exc}")
            return

        self._refresh_after_page_command(session, min(page_index, session.document.page_count - 1))
        self.statusBar().showMessage(f"Page {page_index + 1} deleted | {session.page_count} pages remaining")

    def _on_thumbnail_rows_moved(self, parent, start, end, destination, row) -> None:
        session = self._current_session()
        if session is None:
            return
        if self.thumbnail_list.count() != session.page_count:
            return

        new_order = [
            self.thumbnail_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.thumbnail_list.count())
        ]
        if new_order == list(range(session.page_count)):
            return  # no actual change

        try:
            session.command_history.execute(
                ReorderPagesCommand(self.page_service, session.document, new_order)
            )
        except Exception as exc:
            QMessageBox.critical(self, "Reorder Failed", f"Could not reorder pages:\n{exc}")
            self._load_thumbnails_for_current_session()
            return

        self._refresh_after_page_command(session, max(0, self.thumbnail_list.currentRow()))
        self.statusBar().showMessage(f"Pages reordered | {session.page_count} pages")

    def _undo_current_document(self) -> None:
        session = self._current_session()
        if session is None:
            return
        try:
            command = session.command_history.undo()
        except Exception as exc:
            QMessageBox.critical(self, "Undo Failed", f"Could not undo the last action:\n{exc}")
            return
        if command is None:
            return
        self._refresh_after_page_command(session, session.current_page)
        self.statusBar().showMessage(f"Undid {command.description}")

    def _redo_current_document(self) -> None:
        session = self._current_session()
        if session is None:
            return
        try:
            command = session.command_history.redo()
        except Exception as exc:
            QMessageBox.critical(self, "Redo Failed", f"Could not redo the next action:\n{exc}")
            return
        if command is None:
            return
        self._refresh_after_page_command(session, session.current_page)
        self.statusBar().showMessage(f"Redid {command.description}")

    def _refresh_after_page_command(self, session: DocumentSession, current_page: int) -> None:
        session.page_count = session.document.page_count
        session.page_sizes = self.pdf_adapter.page_sizes(session.document)
        session.current_page = max(0, min(current_page, session.page_count - 1))
        session.page_cache.clear()
        session.thumbnail_cache.clear()
        session.render_queue.clear()
        session.thumbnail_queue = list(range(session.page_count))
        self._set_session_dirty(session, session.command_history.is_dirty)
        self._load_thumbnails_for_current_session()
        self._rebuild_canvas_for_current_session()
        self._restart_search_after_document_change(session)

    def _sync_undo_redo_actions(self, session: DocumentSession | None) -> None:
        history = session.command_history if session is not None else None
        can_undo = history is not None and history.can_undo
        can_redo = history is not None and history.can_redo
        undo_description = history.undo_description if history is not None else ""
        redo_description = history.redo_description if history is not None else ""
        self.undo_action.setEnabled(can_undo)
        self.redo_action.setEnabled(can_redo)
        self.undo_action.setText(f"Undo {undo_description}" if undo_description else "Undo")
        self.redo_action.setText(f"Redo {redo_description}" if redo_description else "Redo")
        self.undo_action.setToolTip(
            f"Undo {undo_description} (Ctrl+Z)" if undo_description else "Undo (Ctrl+Z)"
        )
        self.redo_action.setToolTip(
            f"Redo {redo_description} (Ctrl+Shift+Z)" if redo_description else "Redo (Ctrl+Shift+Z)"
        )

    def _rebuild_canvas_for_current_session(self) -> None:
        """Reset the canvas to loading state and re-queue background rendering."""
        session = self._current_session()
        if session is None:
            return
        self._suspend_canvas_page_sync = True
        session.initial_fit_applied = False
        session.canvas.set_page_count(session.page_count, page_sizes=session.page_sizes)
        self._sync_page_controls(page_count=session.page_count, current_page=session.current_page)
        self._set_thumbnail_selection(session.current_page)
        self._queue_render_for_current_session(center_page=session.current_page)

    def _set_session_dirty(self, session: DocumentSession, dirty: bool) -> None:
        session.is_dirty = dirty
        for tab_index in range(self.tab_widget.count()):
            if self.tab_widget.widget(tab_index) is session.canvas:
                marker = " *" if dirty else ""
                self.tab_widget.setTabText(tab_index, f"{Path(session.path).name}{marker}")
                break
            self._sync_undo_redo_actions(session if session is self._current_session() else self._current_session())
