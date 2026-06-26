"""Provider API keys stored in ~/.perfectrag/keys.yml (chmod 600).

Used by the advisor (Gemini) and by LLM/embedding backends that call external APIs
(OpenAI, Anthropic, Jina, Cohere, etc.). This is distinct from RAG-access keys
(`sk-rag-*`) which live in the generated project's SQLite — see api_keys.py.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import yaml

KEYS_DIR = Path.home() / ".perfectrag"
KEYS_FILE = KEYS_DIR / "keys.yml"

KNOWN_PROVIDERS = {
    "gemini":     "Google Gemini (AIzaSy...)",
    "openai":     "OpenAI (sk-...)",
    "anthropic":  "Anthropic (sk-ant-...)",
    "jina":       "Jina AI (jina_...)",
    "cohere":     "Cohere",
    "groq":       "Groq",
    "firecrawl":  "Firecrawl",
    "tavily":     "Tavily search",
    "brave":      "Brave search",
    "github":     "GitHub PAT",
}


def _chmod_user_only(path: Path) -> None:
    if os.name == "nt":
        return  # NTFS ACLs — user dir already restricted; avoid cross-platform complication
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _load() -> dict:
    if not KEYS_FILE.exists():
        return {}
    data = yaml.safe_load(KEYS_FILE.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _save(data: dict) -> None:
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    KEYS_FILE.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
    _chmod_user_only(KEYS_FILE)


def set_key(provider: str, value: str) -> None:
    provider = provider.lower()
    data = _load()
    data[provider] = value
    _save(data)


def get_key(provider: str) -> str | None:
    """Return key for provider, checking env var first then keys.yml.

    Env precedence lets users override keys.yml per-shell/CI.
    """
    env_name = f"{provider.upper()}_API_KEY"
    env_val = os.environ.get(env_name)
    if env_val:
        return env_val
    return _load().get(provider.lower())


def remove_key(provider: str) -> bool:
    data = _load()
    if provider.lower() in data:
        data.pop(provider.lower())
        _save(data)
        return True
    return False


def list_keys() -> dict[str, str]:
    """Return {provider: masked_value} for display. Known providers included even if empty."""
    data = _load()
    merged: dict[str, str] = {}
    for prov in KNOWN_PROVIDERS:
        raw = data.get(prov)
        env_val = os.environ.get(f"{prov.upper()}_API_KEY")
        if env_val:
            merged[prov] = f"[env] {_mask(env_val)}"
        elif raw:
            merged[prov] = _mask(raw)
        else:
            merged[prov] = ""
    # Also include any custom providers user has stored
    for prov, val in data.items():
        if prov not in merged:
            merged[prov] = _mask(val)
    return merged


def _mask(val: str) -> str:
    if not val:
        return ""
    if len(val) <= 8:
        return "***"
    return f"{val[:4]}…{val[-4:]}"
