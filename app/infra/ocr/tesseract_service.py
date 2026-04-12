from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image


class TesseractService:
    def configure_binary(self, binary_path: str | None) -> None:
        if binary_path:
            pytesseract.pytesseract.tesseract_cmd = binary_path

    def extract_text(self, image_path: str, language: str = "eng") -> str:
        path = Path(image_path)
        with Image.open(path) as image:
            return pytesseract.image_to_string(image, lang=language)
