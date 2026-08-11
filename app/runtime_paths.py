from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resource_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "app" / "resources"
    return project_root() / "app" / "resources"


def app_data_root() -> Path:
    return Path.home() / ".easy_pdf_toolkit"
