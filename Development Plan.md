# PDF Tool Kit Development Plan (Build-Ready)

## 1. Feasibility Analysis

Yes, this tool is feasible to build as an offline desktop app in Python.

What is fully achievable in a robust way:

- PDF viewing, thumbnails, zoom, navigation, search
- Page operations (merge/split/reorder/rotate/delete/insert/extract)
- Annotation and overlay-based editing (text/image/shapes/highlight/stamp/signature)
- OCR pipeline for scanned PDFs/images with selectable language
- Watermark, page numbers, metadata, batch tools

What needs explicit product constraints:

- True in-place editing of existing PDF text is not reliable across arbitrary PDFs
- Compression quality depends on source structure (images/fonts/objects)
- Password removal must only work when user provides authorization/password

Decision:

- Build a production-grade v1 around reliable operations + overlay editing workflow
- Present advanced editing honestly in UI as "Overlay/Replace" and not "native text rewrite"

## 2. Product Scope

### 2.0 Product Direction (Visual First)

Primary product goal for this project is now:

- Fast offline PDF workflow with a polished, modern reader experience
- Theme quality (dark/light + reading comfort) treated as a core feature, not cosmetic polish
- Viewer UX parity target: browser-grade responsiveness and discoverable controls

### 2.1 MVP (must ship first)

1. File operations: open/new/save/save as/recent files/drag drop
2. Viewer: thumbnails, zoom, fit width/page, page nav, text search highlight, fit-to-width, fit-to-height
3. Page tools: reorder/delete/rotate/insert blank/extract/merge/split
4. Reader UX: bookmarks/TOC panel, fullscreen (F11), presentation mode (F5), printable output
5. Theme system: robust dark/light palettes, persistent theme preference, theme-aware icons/widgets
6. Reading comfort: night reading mode (PDF color inversion independent from app theme)
7. Search UX: Ctrl+F bar with next/prev, live highlights, match counters
8. Editing: add text, image, highlight, underline, strikeout, sticky note, freehand draw
9. Utilities: watermark, page numbers
10. OCR: scanned PDF + image to searchable PDF (manual trigger only)
11. Export: selected pages, save optimized copy

### 2.2 Post-MVP (v1.1/v1.2)

1. Forms: fill/flatten forms
2. Signature workflow: image signature + pen signature + timestamp
3. Metadata editor full panel
4. Password protect/remove (authorized flow)
5. Batch toolbox (merge/split/watermark/ocr/images to pdf)
6. Advanced theme polish: density presets, compact mode, refined motion/hover states
7. Keyboard shortcut customization
8. Auto-update flow with release notes
9. Multi-language UI foundation

### 2.3 Future (v2)

1. Plugin system for custom processors
2. Compare two PDFs (visual/text differences)
3. Redaction workflow with preview and irreversible apply
4. Watch-folder automation

## 3. Missing Pieces Added (Critical)

The previous plan was feature-rich but missing execution details. Add these mandatory pieces:

1. Architecture contract

- Strict separation: UI, application services, PDF adapters, persistence, worker jobs

2. Command model and undo/redo

- Every editor action represented as command object with do/undo

3. Document state model

- Dirty state tracking, unsaved changes guard, autosave snapshots

4. Job system

- Background queue for OCR, batch jobs, heavy exports, compression
- Progress + cancellation support

5. Error taxonomy

- User-safe errors (friendly)
- Developer logs (debug detail)

6. Settings and profile

- Persistent settings file for theme, OCR language, Tesseract path, defaults

7. Test strategy

- Unit tests for services
- Integration tests for PDF pipeline
- Golden-file tests for deterministic output checks

8. Release and packaging

- Windows executable packaging pipeline
- Versioning and migration for settings format

9. Security and privacy

- Fully offline guarantee
- No telemetry by default
- Temporary files cleaned securely

10. Performance targets

- Open 300-page PDF under target threshold
- Smooth scrolling with thumbnail virtualization

## 4. Recommended Tech Stack

- GUI: PySide6 (Qt for Python)
- Core PDF engine: PyMuPDF (fitz)
- Supplemental PDF ops: pypdf
- OCR: pytesseract + Pillow
- Optional image preprocessing for OCR: opencv-python
- Data models: pydantic (optional but recommended)
- Logging: standard logging + rotating file handler
- Tests: pytest
- Build/package: PyInstaller

## 5. Proposed Project Structure

```text
easy-pdf-tool-kit/
  app/
    main.py
    bootstrap.py
    ui/
      main_window.py
      panels/
      dialogs/
      widgets/
    core/
      models/
      commands/
      services/
      jobs/
      events/
    infra/
      pdf_engines/
        pymupdf_adapter.py
        pypdf_adapter.py
      ocr/
        tesseract_service.py
      storage/
        settings_repo.py
        recent_files_repo.py
      logging/
    resources/
      icons/
      themes/
  tests/
    unit/
    integration/
    golden/
  scripts/
  requirements.txt
  README.md
  DEVELOPMENT.md
```

## 6. Architecture Blueprint

### 6.1 Layers

1. Presentation layer (Qt Widgets)
2. Application layer (use cases and commands)
3. Domain layer (document/page/annotation state)
4. Infrastructure layer (PDF/OCR/filesystem implementations)

### 6.2 Core Services

1. DocumentService: open/save/export/recent/dirty state
2. ViewerService: render page pixmap/cache/search index
3. PageService: reorder/insert/delete/rotate/extract/merge/split/crop
4. AnnotationService: text/image/shapes/highlight/notes/signature
5. OcrService: OCR execution and text layer insertion
6. UtilityService: watermark/page numbers/metadata/password/compression
7. BatchService: multi-file queue operations
8. JobManager: background workers + progress + cancellation

### 6.3 State and Events

- AppState: active document, selection, zoom, tool mode, theme
- Domain events: DocumentOpened, PageChanged, SelectionChanged, JobProgress
- Event bus for decoupling UI refresh from service logic

## 7. Feature Specification (Practical)

### 7.1 Editing model for existing text

- Mode A: Overlay text box on top of original content
- Mode B: Redaction + replacement text insertion
- UI wording must clearly indicate limitations and expected output

### 7.2 OCR model

- Manual action only
- Per page range or whole document
- OCR language selector with installed language detection
- Store text layer into output PDF
- If OCR fails, preserve original file and show actionable error

### 7.3 Batch model

- Input file list + destination + naming template
- Preview summary before execution
- Detailed result report: success, failed file, reason

### 7.4 Search model

- In-document text search with next/previous navigation
- Highlight all matches on current page
- Optional match-case/whole-word

## 8. UX and Interaction Standards

1. Main layout:

- Top toolbar (file/view/edit/page/tools)
- Left thumbnail panel (virtualized)
- Center canvas (scroll + zoom)
- Right property/annotation panel
- Bottom status bar (page, zoom, job status)

2. Multi-document:

- Tabbed documents with dirty indicators

3. Productivity:

- Context menus in thumbnail and canvas
- Keyboard shortcuts
- Recent actions list

4. Reliability UX:

- Non-blocking progress dialogs for long jobs
- Cancel support for jobs
- Crash-safe recovery prompt on restart

5. Accessibility:

- Scalable UI fonts
- High-contrast theme option
- Keyboard-first operation for major flows

## 9. Visual Design System Plan (High Priority)

1. Design tokens first:

- Central token file for color, spacing, radius, typography, elevation, border contrast
- Separate semantic tokens for viewer canvas, workspace bars, side panels, and status states

2. Theme architecture:

- Full dark and light theme parity (all widgets, dialogs, icons, overlays)
- Theme preference persisted in settings and restored on launch
- Runtime theme switch with immediate icon recolor and canvas background adaptation

3. Reader-specific visual modes:

- App theme (dark/light)
- Night reading mode (PDF inversion) independent from app theme

4. UI composition target:

- Workspace bar with compact icon controls (Open, TOC, Search, Zoom, Page nav, Theme)
- Optional collapsible left navigation rail for tools
- Tabbed viewer with clean active tab emphasis and minimal chrome

5. Consistency rules:

- All reusable headers/action bars generated by shared UI factories
- No ad-hoc inline style strings for production screens except for temporary prototypes

## 10. Competitive Feature Benchmark (Inspired by PDFApps)

The following capabilities are now explicit benchmark targets for this project:

1. Integrated reader:

- Tabbed multi-document viewing
- Continuous scroll + lazy rendering with viewport buffer
- Ctrl+scroll zoom, fit width/page controls, page jump input
- Bookmarks/TOC side panel when outline exists
- Full-text search with live highlight navigation
- Print with high-resolution rendering
- Fullscreen and presentation modes

2. Reader productivity:

- Drag and drop open
- Recent files with dedupe and quick reopen
- Keyboard shortcuts for core reader actions

3. Editing baseline:

- Visual editing workflows (highlight, redact, text/image overlays, notes)
- Undo/redo backbone for editor actions

4. Theme and polish:

- Modern dark/light system with robust component coverage
- Theme-aware icons and dialogs
- Professional spacing, typography, and hierarchy in every panel

5. Platform maturity:

- Packaging for Windows/Linux/macOS
- Optional updater and release-channel strategy

## 11. Performance and Quality Targets

1. Open PDF up to 300 pages within acceptable desktop time budget
2. Thumbnail rendering lazy-loaded and cached
3. Smooth scrolling at normal zoom on mid-range machines
4. Long tasks never freeze UI thread
5. No data loss on crash during save (atomic save via temp file + rename)

## 12. Security and Compliance

1. Fully offline operation
2. No cloud API dependency
3. No automatic outbound telemetry
4. Sensitive temp files cleaned after operation
5. Password operations require explicit user intent and warnings

## 13. Delivery Roadmap (Visual + Feature)

### Phase A (Immediate)

1. Stabilize virtualized rendering (viewport window + cache eviction + prefetch direction)
2. Implement fit-width mode and search bar UX parity
3. Introduce theme token module and migrate current styles to tokenized QSS

### Phase B (Reader Parity)

1. Bookmarks/TOC panel from PDF outline
2. Fullscreen (F11) and presentation mode (F5)
3. Night reading mode independent from app theme
4. Print pipeline with high-resolution output

### Phase C (Tooling + Editor)

1. Expand page tools to merge/split/extract polish workflows
2. Add editor action history (undo/redo)
3. Signature and annotation quality pass

### Phase D (Product Maturity)

1. Packaging and installer polish
2. Optional auto-update mechanism
3. Multi-language architecture and localization rollout

## 14. Testing Strategy

1. Unit tests

- Command handlers, services, settings persistence

2. Integration tests

- Open/edit/save/merge/split/OCR pipelines

3. Golden-file tests

- Compare expected output PDF properties/content markers

4. UI smoke tests

- Basic launch/open/render/search/edit/save flows

5. Regression suite

- Known problematic PDFs (scanned, rotated, forms, encrypted)

## 15. Delivery Plan (8 Weeks)

### Week 1

- Project scaffolding, architecture skeleton, settings/logging, basic window shell

### Week 2

- Open/save/recent files, viewer canvas, zoom/navigation, thumbnail sidebar

### Week 3

- Search, page rotate/delete/insert/reorder/extract, undo-redo framework

### Week 4

- Merge/split, watermark/page numbers, export selected pages

### Week 5

- Annotation tools: text/image/highlight/shape/freehand/sticky note

### Week 6

- OCR pipeline + language management + background jobs + cancellation

### Week 7

- Batch tools + metadata panel + forms fill/flatten + signature basics

### Week 8

- Stabilization, test hardening, packaging, installer, README and user docs

## 16. Definition of Done for MVP

MVP is complete only if all are true:

1. App launches with no manual code edits
2. Can open, view, search, annotate, and save PDF reliably
3. Can merge/split/reorder/delete/rotate pages
4. OCR works on at least one scanned sample and creates searchable output
5. Long jobs run in workers and UI remains responsive
6. No critical crash in smoke test set
7. README includes install/run/known limitations

## 17. First Build Backlog (Start Immediately)

1. Initialize repository layout and dependency baseline
2. Implement main window with 5-region layout and tab support
3. Build document open/render/thumbnail pipeline with PyMuPDF
4. Add zoom/navigation/search controls
5. Implement page operations: rotate/delete/reorder/insert blank/extract
6. Add save/save as/export selected pages
7. Add annotation primitives (text/image/highlight)
8. Add watermark/page numbers
9. Add OCR job flow (single document first, then batch)
10. Add tests + packaging script

## 18. Risks and Mitigations

1. Risk: Editing expectations too high for arbitrary PDFs

- Mitigation: Product messaging and overlay/redaction workflows

2. Risk: OCR speed and quality variance

- Mitigation: Language selection, image preprocessing toggle, batch queue

3. Risk: UI lag on large files

- Mitigation: lazy rendering, caching, worker threads, profiling

4. Risk: Save corruption

- Mitigation: atomic write strategy and backup recovery

5. Risk: Scope creep

- Mitigation: freeze MVP scope until Definition of Done passes

---

This plan is now implementation-ready. Next action is to scaffold the codebase and execute Week 1 backlog.
