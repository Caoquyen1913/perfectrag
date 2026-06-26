"""IBM Docling parser — best for tables + complex layouts."""

from __future__ import annotations


class DoclingParser:
    def __init__(self):
        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            raise RuntimeError("docling not installed. `pip install docling`")
        self._conv = DocumentConverter()

    def parse(self, path: str) -> str:
        result = self._conv.convert(path)
        return result.document.export_to_markdown()
