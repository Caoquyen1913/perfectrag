"""Embedded Python library — RAG runtime without Docker.

    from perfectrag import RAG
    rag = RAG.from_config("perfectrag.yml")
    rag.ingest("./docs")
    print(rag.query("What is RAG?"))
"""

from perfectrag.core.agent import AgentResult, AgentStep
from perfectrag.core.extensions import (
    REGISTRY,
    Context,
    Document,
    Extension,
    inject,
    load_extensions,
    retrieve,
    skill,
    tool,
    transform,
)
from perfectrag.core.rag import RAG

__all__ = [
    "RAG",
    "REGISTRY",
    "AgentResult",
    "AgentStep",
    "Context",
    "Document",
    "Extension",
    "inject",
    "load_extensions",
    "retrieve",
    "skill",
    "tool",
    "transform",
]
