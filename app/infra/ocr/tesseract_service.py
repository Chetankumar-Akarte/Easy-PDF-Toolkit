from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytesseract
from PIL import Image


class TesseractService:
    @staticmethod
    def _candidate_paths() -> list[Path]:
        candidates: list[Path] = []
        if sys.platform.startswith("win"):
            candidates.extend(
                [
                    Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
                    Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
                ]
            )
        else:
            candidates.extend(
                [
                    Path("/opt/homebrew/bin/tesseract"),
                    Path("/usr/local/bin/tesseract"),
                    Path("/usr/bin/tesseract"),
                ]
            )
        return candidates

    def resolve_binary(self, configured_path: str | None = None) -> str | None:
        if configured_path:
            configured = Path(configured_path).expanduser()
            if configured.exists():
                return str(configured)

        discovered = shutil.which("tesseract")
        if discovered:
            return discovered

        for candidate in self._candidate_paths():
            if candidate.exists():
                return str(candidate)
        return None

    def configure_binary(self, binary_path: str | None) -> None:
        resolved = self.resolve_binary(binary_path)
        if resolved:
            pytesseract.pytesseract.tesseract_cmd = resolved

    def is_available(self, configured_path: str | None = None) -> bool:
        return self.resolve_binary(configured_path) is not None

    def help_text(self) -> str:
        if sys.platform.startswith("win"):
            return (
                "Tesseract OCR is not installed. Install it from the Tesseract project page "
                "and set the executable path in app settings, for example: "
                "C:/Program Files/Tesseract-OCR/tesseract.exe"
            )
        if sys.platform == "darwin":
            return (
                "Tesseract OCR is not installed. Install it with Homebrew (brew install tesseract) "
                "or set a custom executable path in app settings."
            )
        return (
            "Tesseract OCR is not installed. Install it with your package manager "
            "(for example: sudo apt install tesseract-ocr) or set a custom path in app settings."
        )

    def extract_text(self, image_path: str, language: str = "eng") -> str:
        resolved = self.resolve_binary(getattr(pytesseract.pytesseract, "tesseract_cmd", ""))
        if not resolved:
            raise RuntimeError(self.help_text())
        pytesseract.pytesseract.tesseract_cmd = resolved

        path = Path(image_path)
        with Image.open(path) as image:
            return pytesseract.image_to_string(image, lang=language)
