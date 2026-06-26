"""Embedded Python library — RAG runtime without Docker.

    from perfectrag import RAG
    rag = RAG.from_config("perfectrag.yml")
    rag.ingest("./docs")
    print(rag.query("What is RAG?"))
"""

from perfectrag.core.rag import RAG

__all__ = ["RAG"]
