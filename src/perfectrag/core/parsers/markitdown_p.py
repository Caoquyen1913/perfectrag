"""Microsoft MarkItDown parser — fast, broad format support."""

from __future__ import annotations


class MarkItDownParser:
    def __init__(self):
        try:
            from markitdown import MarkItDown
        except ImportError:
            raise RuntimeError("markitdown not installed. `pip install markitdown`")
        self._md = MarkItDown()

    def parse(self, path: str) -> str:
        return self._md.convert(path).text_content
