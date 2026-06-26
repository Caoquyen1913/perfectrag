"""Document parsers."""

from __future__ import annotations

from perfectrag.core.protocols import Parser

SUPPORTED = ["markitdown", "docling", "simple"]


def build(name: str = "markitdown") -> Parser:
    name = name.lower()
    if name == "markitdown":
        from perfectrag.core.parsers.markitdown_p import MarkItDownParser
        return MarkItDownParser()
    if name == "docling":
        from perfectrag.core.parsers.docling_p import DoclingParser
        return DoclingParser()
    if name == "simple":
        from perfectrag.core.parsers.simple import SimpleParser
        return SimpleParser()
    raise ValueError(f"Unknown parser: {name}")
