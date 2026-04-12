from pathlib import Path

from app.infra.storage.settings_repo import AppSettings, SettingsRepository


def test_settings_round_trip(tmp_path: Path) -> None:
    repo = SettingsRepository(tmp_path)
    expected = AppSettings(theme="dark", tesseract_path="C:/tesseract/tesseract.exe", ocr_language="eng")

    repo.save(expected)
    loaded = repo.load()

    assert loaded == expected
