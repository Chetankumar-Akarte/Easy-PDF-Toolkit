from __future__ import annotations

import argparse
from pathlib import Path

from PySide6.QtCore import QTimer

from app.bootstrap import create_application


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Easy PDF Tool Kit")
    parser.add_argument(
        "--smoke-open",
        metavar="PDF_PATH",
        help="Open a PDF and exit automatically with success/failure status.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    app, window = create_application()

    smoke_open = args.smoke_open
    if smoke_open:
        pdf_path = Path(smoke_open).expanduser().resolve()
        if not pdf_path.exists():
            return 2

        window.show()
        opened = window.open_document_for_smoke(str(pdf_path))
        if not opened:
            QTimer.singleShot(0, app.quit)
            app.exec()
            return 3

        QTimer.singleShot(1200, app.quit)
        app.exec()
        return 0

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
