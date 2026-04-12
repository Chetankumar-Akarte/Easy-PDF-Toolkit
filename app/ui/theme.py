from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette


@dataclass(frozen=True)
class ThemeColors:
    name: str
    bg_window: str
    bg_panel: str
    bg_elevated: str
    bg_input: str
    border: str
    text_primary: str
    text_secondary: str
    accent: str
    accent_hover: str
    danger: str
    icon: str


LIGHT_THEME = ThemeColors(
    name="light",
    bg_window="#f3f6fb",
    bg_panel="#ffffff",
    bg_elevated="#f7f9fd",
    bg_input="#ffffff",
    border="#d2d9e6",
    text_primary="#1f2937",
    text_secondary="#5f6b7a",
    accent="#0f766e",
    accent_hover="#0b5f59",
    danger="#b42318",
    icon="#334155",
)

DARK_THEME = ThemeColors(
    name="dark",
    bg_window="#0e141b",
    bg_panel="#121a24",
    bg_elevated="#182330",
    bg_input="#1b2836",
    border="#2c3c4f",
    text_primary="#e5edf6",
    text_secondary="#9aafc4",
    accent="#2dd4bf",
    accent_hover="#1bb8a5",
    danger="#f97066",
    icon="#d8e2ee",
)


def get_theme(theme_name: str) -> ThemeColors:
    return DARK_THEME if theme_name == "dark" else LIGHT_THEME


def make_palette(theme: ThemeColors) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(theme.bg_window))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(theme.text_primary))
    palette.setColor(QPalette.ColorRole.Base, QColor(theme.bg_input))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(theme.bg_elevated))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(theme.bg_panel))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(theme.text_primary))
    palette.setColor(QPalette.ColorRole.Text, QColor(theme.text_primary))
    palette.setColor(QPalette.ColorRole.Button, QColor(theme.bg_panel))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(theme.text_primary))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.accent))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    return palette


def build_qss(theme: ThemeColors) -> str:
    return f"""
QMainWindow {{
    background: {theme.bg_window};
    color: {theme.text_primary};
}}
QWidget {{
    color: {theme.text_primary};
    font-family: 'Josefin Sans', 'Segoe UI', 'Nirmala UI', Arial, sans-serif;
    font-size: 12pt;
}}
QMenuBar, QMenu {{
    background: {theme.bg_panel};
    border: 1px solid {theme.border};
}}
QMenu::item:selected {{
    background: {theme.bg_elevated};
}}
QStatusBar {{
    background: {theme.bg_panel};
    border-top: 1px solid {theme.border};
    color: {theme.text_secondary};
}}
QListWidget#thumbnailList, QListWidget#welcomeList {{
    background: {theme.bg_panel};
    border-right: 1px solid {theme.border};
}}
QListWidget#thumbnailList::item {{
    padding: 4px;
    margin: 2px;
}}
QListWidget#thumbnailList::item:selected, QListWidget#welcomeList::item:selected {{
    background: {theme.bg_elevated};
    border: 1px solid {theme.accent};
}}
QTreeWidget#tocTree {{
    background: {theme.bg_panel};
    border-right: 1px solid {theme.border};
    outline: none;
}}
QWidget#tocPanel {{
    background: {theme.bg_panel};
    border-right: 1px solid {theme.border};
}}
QWidget#tocHeader {{
    background: {theme.bg_elevated};
    border-bottom: 1px solid {theme.border};
}}
QToolButton#tocEdgeToggle {{
    background: {theme.bg_panel};
    border: 1px solid {theme.border};
    border-radius: 4px;
}}
QToolButton#tocEdgeToggle:hover {{
    border-color: {theme.accent};
}}
QTreeWidget#tocTree::item {{
    padding: 4px 6px;
}}
QTreeWidget#tocTree::item:selected {{
    background: {theme.bg_elevated};
    border: 1px solid {theme.accent};
}}
QScrollArea#pdfScrollArea {{
    background: {theme.bg_window};
    border: none;
}}
QScrollArea#pdfScrollArea[nightMode="true"], QWidget#pdfCanvasContainer[nightMode="true"] {{
    background: #000000;
}}
QLabel#pdfPage {{
    background: #ffffff;
    border: 1px solid {theme.border};
}}
QLabel#pdfPage[nightMode="true"] {{
    background: #000000;
    border: 1px solid #111827;
}}
QLabel#pdfPageLoading {{
    background: {theme.bg_panel};
    border: 1px dashed {theme.border};
    color: {theme.text_secondary};
}}
QLabel#pdfPageLoading[nightMode="true"] {{
    background: #090b0f;
    border: 1px dashed #334155;
    color: #a0b1c5;
}}
QTabWidget#documentTabs::pane {{
    border: 1px solid {theme.border};
    background: {theme.bg_panel};
}}
QTabBar::tab {{
    background: {theme.bg_elevated};
    color: {theme.text_secondary};
    border: 1px solid {theme.border};
    padding: 5px 10px;
    margin-right: 1px;
}}
QTabBar::tab:selected {{
    color: {theme.text_primary};
    border-bottom: 2px solid {theme.accent};
}}
QWidget#actionBar {{
    background: {theme.bg_elevated};
    border-bottom: 1px solid {theme.border};
}}
QWidget#actionBar QToolButton, QWidget#readerControls QToolButton {{
    background: {theme.bg_panel};
    border: 1px solid {theme.border};
    border-radius: 4px;
}}
QWidget#actionBar QToolButton:hover, QWidget#readerControls QToolButton:hover {{
    border-color: {theme.accent};
}}
QWidget#actionBar QToolButton:disabled, QWidget#readerControls QToolButton:disabled {{
    color: {theme.text_secondary};
    background: {theme.bg_elevated};
}}
QWidget#readerControls {{
    background: {theme.bg_elevated};
    border-top: 1px solid {theme.border};
    color: {theme.text_primary};
}}
QWidget#readerControls QLabel {{
    color: {theme.text_primary};
}}
QToolButton#nightModeBadge {{
    background: {theme.bg_panel};
    border: 1px solid {theme.border};
    border-radius: 4px;
    padding: 0;
}}
QToolButton#nightModeBadge:hover {{
    background: {theme.bg_elevated};
    border-color: {theme.accent};
}}
QToolButton#nightModeBadge[active="true"] {{
    border-color: {theme.accent};
    background: {theme.bg_elevated};
}}
QWidget#readerControls QSpinBox {{
    background: {theme.bg_input};
    border: 1px solid {theme.border};
    color: {theme.text_primary};
}}
QSpinBox {{
    background: {theme.bg_input};
    border: 1px solid {theme.border};
    border-radius: 4px;
    padding: 2px 6px;
}}
QMessageBox, QDialog {{
    background: {theme.bg_panel};
}}
QWidget#propertiesPanel {{
    background: {theme.bg_panel};
    border-left: 1px solid {theme.border};
}}
"""
