from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.infra.logging.log_config import configure_logging
from app.infra.storage.recent_files_repo import RecentFilesRepository
from app.infra.storage.settings_repo import SettingsRepository
from app.ui.main_window import MainWindow


def create_application() -> tuple[QApplication, MainWindow]:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName("Easy PDF Tool Kit")
    app.setOrganizationName("EasyPDF")
    app_icon = Path(__file__).resolve().parent / "resources" / "icons" / "tool_logo.svg"
    if app_icon.exists():
        app.setWindowIcon(QIcon(str(app_icon)))

    configure_logging()

    workspace_root = Path(__file__).resolve().parents[1]
    settings_repo = SettingsRepository(workspace_root)
    recent_files_repo = RecentFilesRepository(workspace_root)

    main_window = MainWindow(settings_repo=settings_repo, recent_files_repo=recent_files_repo)
    return app, main_window
