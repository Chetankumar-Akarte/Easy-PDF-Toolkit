class PyPDFAdapter:
    """Thin wrapper for pypdf operations used for merge/split/encryption."""

    def create_reader(self, path: str):
        from pypdf import PdfReader

        return PdfReader(path)
