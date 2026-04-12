from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class AppSettings:
    theme: str = "light"
    night_mode: bool = False
    tesseract_path: str = ""
    ocr_language: str = "eng"
    window_x: int | None = None
    window_y: int | None = None
    window_width: int | None = None
    window_height: int | None = None
    last_open_dir: str = ""


class SettingsRepository:
    def __init__(self, workspace_root: Path) -> None:
        self._settings_path = workspace_root / ".easy_pdf_toolkit" / "settings.json"

    def load(self) -> AppSettings:
        if not self._settings_path.exists():
            return AppSettings()

        data = json.loads(self._settings_path.read_text(encoding="utf-8"))
        return AppSettings(**{**asdict(AppSettings()), **data})

    def save(self, settings: AppSettings) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings_path.write_text(json.dumps(asdict(settings), indent=2), encoding="utf-8")
