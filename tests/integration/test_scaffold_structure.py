from pathlib import Path


def test_scaffold_expected_paths_exist() -> None:
    root = Path(__file__).resolve().parents[2]

    expected_paths = [
        root / "app" / "main.py",
        root / "app" / "bootstrap.py",
        root / "app" / "ui" / "main_window.py",
        root / "app" / "infra" / "pdf_engines" / "pymupdf_adapter.py",
        root / "requirements.txt",
    ]

    assert all(path.exists() for path in expected_paths)
