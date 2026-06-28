"""perfectRAG — dynamic RAG framework scaffolder + embedded Python library."""

__version__ = "1.4.0"

# Top-level exports for library mode:
#   from perfectrag import RAG, inject, retrieve, transform, tool, skill, Document
from perfectrag.core import (
    RAG,
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

__all__ = [
    "RAG",
    "REGISTRY",
    "Context",
    "Document",
    "Extension",
    "__version__",
    "inject",
    "load_extensions",
    "retrieve",
    "skill",
    "tool",
    "transform",
]
