"""Zero-dep fallback parser: pypdf for PDFs, plain read for text."""

from __future__ import annotations

from pathlib import Path


class SimpleParser:
    def parse(self, path: str) -> str:
        p = Path(path)
        if p.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError:
                raise RuntimeError("pypdf not installed for PDF fallback.")
            return "\n".join((page.extract_text() or "") for page in PdfReader(str(p)).pages)
        return p.read_text(encoding="utf-8", errors="ignore")
