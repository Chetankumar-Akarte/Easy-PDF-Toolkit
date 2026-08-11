# Easy PDF Tool Kit

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue)
![PySide6](<https://img.shields.io/badge/UI-PySide6%20(Qt%206)-41CD52>)
![PyMuPDF](https://img.shields.io/badge/PDF-PyMuPDF-orange)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-6f42c1)
![Status](https://img.shields.io/badge/Status-Active%20Development-0a7ea4)

A desktop-first, fully offline PDF toolkit built with Python and PySide6. View, navigate, and edit PDF documents without uploading files to any server or cloud service.

> **Status:** Active development — advanced reader experience is ready; editing and annotation features are in progress.

---

## Features

### Implemented

- **PDF Viewer** — Multi-tab document viewer with smooth zoom, fit-to-width and fit-to-height modes, viewport-stable scroll, and better HiDPI rendering
- **Thumbnail Panel** — Sidebar thumbnail strip with animated circular loading indicators, background generation, and immediate click-to-navigate with selected-page priority
- **TOC / Bookmarks Panel** — Toggleable outline panel with collapse control for fast section navigation
- **Page Navigation** — First / Previous / Next / Last page controls and page number input
- **Display Modes** — Continuous and Single Page reading modes (menu + bottom quick toggle)
- **Reading Modes** — Light / dark app themes and Night Reading Mode (PDF invert) with quick toggle
- **Zoom Controls** — Zoom in / out / reset with customizable level, viewport anchor preserved on zoom
- **Text Search** — Ribbon and `Ctrl+F` access, case-insensitive document search with debounced page-by-page scanning, all-match highlights, active-result focus, wraparound navigation, per-tab state, and no-results feedback
- **File Operations** — Open, Save (incremental), Save As with overwrite confirmation, Close tab, and Merge PDFs with ordered inputs, per-file page ranges, progress/cancellation, overwrite safety, and automatic result opening
- **Page Tools** — Rotate left/right, delete, reorder, and insert 1–100 blank pages before/after the current page using current/A4/Letter/Legal sizes and portrait/landscape orientation; Split / Extract Pages workflow supports current page, custom ranges, and split by size
- **Undo / Redo** — Per-document command history for rotate, delete, reorder, and blank-page insertion with saved-state-aware dirty markers
- **Text Markup Annotations** — Rotation-safe drag selection with visual feedback, native PDF Highlight / Underline / Strikeout annotations, annotation hit-testing and selection outlines, Properties details, context-menu/ribbon/Delete-key removal, save persistence, and per-document undo/redo
- **Sticky Notes** — Click-to-place native PDF sticky notes with editable content, annotation selection outlines, Properties inspection, context-menu/ribbon operations, Delete-key removal with confirmation, and per-document undo/redo with save persistence
- **Image Extraction** — Export all unique embedded images from the open PDF, or right-click a displayed image to extract it individually in its original detected format
- **Recent Documents** — Welcome screen lists last 10 opened files sorted by most recently opened; click to reopen; missing files are cleaned up automatically; clear history action included
- **Persistent Settings** — Window size, position, and last-used folder remembered between launches
- **Keyboard Shortcuts** — `Ctrl+Z` Undo, `Ctrl+Shift+Z` Redo, `Alt+T` Select Text, `Alt+A` Select Annotation, `Alt+N` Add Sticky Note mode, `Ctrl+Alt+N` Edit selected Sticky Note, `Delete` Delete Annotation, `Ctrl+Alt+H` Highlight, `Ctrl+Alt+U` Underline, `Ctrl+Alt+K` Strikeout, `Ctrl+F` Find, `Enter` / `Shift+Enter` next/previous match, `Esc` close search, `Ctrl+Shift+M` Merge PDFs, `Ctrl+Shift+B` Insert Blank Pages, `Ctrl+O` Open, `Ctrl+S` Save, `Ctrl+Shift+S` Save As, `Ctrl+Shift+W` Close, `Ctrl+W` Fit Width, `Ctrl+R` Night Reading Mode, `Ctrl+X` Split / Extract Pages, `Ctrl+Q` Exit
- **About Dialog** — Help > About with app metadata, runtime details, and repository link

### Roadmap

- Rendering parity polish — final quality alignment with reference viewer in all zoom/night scenarios
- Annotations — text boxes and freehand draw
- Overlay editing — add text boxes, images, shapes, stamps, signatures
- Utilities — watermark, page numbering
- OCR — scanned PDF / image to searchable PDF (offline, Tesseract)
- Batch tools — merge, split, compress, watermark, OCR across multiple files
- Forms — fill and flatten PDF forms
- Password — protect and remove (authorized flow only)

---

## Tech Stack

| Layer            | Library                                                                 |
| ---------------- | ----------------------------------------------------------------------- |
| UI Framework     | [PySide6](https://doc.qt.io/qtforpython/) (Qt 6)                        |
| PDF Rendering    | [PyMuPDF (fitz)](https://pymupdf.readthedocs.io/)                       |
| PDF Manipulation | [pypdf](https://pypdf.readthedocs.io/)                                  |
| OCR (planned)    | [Tesseract](https://github.com/tesseract-ocr/tesseract) via pytesseract |
| Language         | Python 3.11+                                                            |

---

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Windows, macOS, or Linux

### Installation

```powershell
# Clone the repository
git clone https://github.com/Chetankumar-Akarte/Easy-PDF-Toolkit.git
cd Easy-PDF-Toolkit

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell
# source .venv/bin/activate        # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

### Run

```powershell
python -m app.main
```

### Build Binaries (Manual Control)

- GitHub Actions manual workflow: `.github/workflows/release.yml`
- Workflow outputs:
	- Portable: zip (Windows), tar.gz (macOS/Linux)
	- Installers: MSI (Windows), DMG/PKG (macOS), AppImage (Linux)
- Signing: Windows (Authenticode), macOS (codesign + notarization), Linux (GPG detached signatures)
- Linux release also includes `linux-signing-public-key.asc` for end-user signature verification.
- The workflow runs packaged smoke tests before publishing artifacts.
- Local scripts:
	- macOS/Linux: `bash scripts/release/build_local.sh 1.0.0 both`
	- Windows PowerShell: `./scripts/release/build_local.ps1 -Version 1.0.0 -ArtifactKind both`

See `RELEASE.md` for full release details.

### OCR Prerequisite

OCR uses Tesseract as an external dependency and is not bundled in binaries.

- Windows: install Tesseract and set path if needed (for example: `C:/Program Files/Tesseract-OCR/tesseract.exe`)
- macOS: `brew install tesseract`
- Linux: install `tesseract-ocr` via your package manager

### Repository

- GitHub Repo: [https://github.com/Chetankumar-Akarte/Easy-PDF-Toolkit](https://github.com/Chetankumar-Akarte/Easy-PDF-Toolkit)

---

## Screenshots

### Dashboard

![Dashboard](screenshot/01_Easy-PDF-Reader-Dashboard.png)

### Menus

![Menus](screenshot/02_Reader-Menus.png)

### Dark Mode

![Dark Mode](screenshot/03_Easy-PDF-Reader-Dark-Mode.png)

### Light Mode

![Light Mode](screenshot/04_Easy-PDF-Reader-Light-Mode.png)

### Night Reading Mode

![Night Reading Mode](screenshot/05_Easy-PDF-Reader-Reading-Mode.png)

### Fit To Width

![Fit To Width](screenshot/06_Easy-PDF-Reader-Page-Width.png)

### Continuous Reading

![Continuous Reading](screenshot/07_Easy-PDF-Reader-Continue-Reading.png)

### About Dialog

![About Dialog](screenshot/08_Easy-PDF-Reader-About.png)

### Split / Extract Pages

![Split / Extract Pages](screenshot/09_Easy-PDF-Reader-Split-Extract_Pages.png)

---

## Project Structure

```
Easy-PDF-Toolkit/
├── app/
│   ├── main.py                  # Entry point
│   ├── bootstrap.py             # App bootstrap / DI wiring
│   ├── ui/
│   │   ├── main_window.py       # Main application window
│   │   ├── widgets/
│   │   │   └── pdf_canvas.py    # Scrollable multi-page PDF canvas
│   │   ├── panels/              # Thumbnail panel, side panels
│   │   └── dialogs/             # About and other dialogs
│   ├── core/
│   │   ├── services/            # DocumentService, PageService (business logic)
│   │   ├── models/              # Domain models and dataclasses
│   │   ├── commands/            # Command objects for undo/redo
│   │   └── jobs/                # Background job definitions
│   ├── infra/
│   │   ├── pdf_engines/         # PyMuPDF and pypdf adapters
│   │   ├── storage/             # Settings and recent files persistence
│   │   ├── ocr/                 # Tesseract adapter
│   │   └── logging/             # Structured logging setup
│   └── resources/
│       ├── icons/               # SVG toolbar icons
│       └── themes/              # Light / dark theme stylesheets
├── tests/
│   ├── unit/
│   ├── integration/
│   └── golden/
├── scripts/                     # Helper / maintenance scripts
├── screenshot/                  # App screenshots used in this README
├── requirements.txt
└── Development Plan.md          # Full roadmap and execution plan
```

---

## Contributing

1. Fork the repository and create a feature branch.
2. Follow the layered architecture — UI code stays in `app/ui`, business logic in `app/core`, I/O in `app/infra`.
3. Run `python -m compileall app` before submitting a pull request.
4. Open an issue first for large features or breaking changes.

---

## Author

**Chetankumar Akarte**

- GitHub: [@Chetankumar-Akarte](https://github.com/Chetankumar-Akarte)

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
