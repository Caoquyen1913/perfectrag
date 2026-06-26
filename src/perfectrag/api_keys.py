"""RAG-access API keys (`sk-rag-*`) stored in project-level SQLite.

Separate from ~/.perfectrag/keys.yml (which stores provider keys for external APIs).
These keys gate the Query API: `POST /v1/query` etc. Each key has rate-limit + usage.
"""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys (
    key TEXT PRIMARY KEY,
    name TEXT,
    rate_per_minute INTEGER DEFAULT 60,
    revoked INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT,
    endpoint TEXT,
    ts TEXT DEFAULT (datetime('now')),
    status INTEGER,
    tokens INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_usage_key_ts ON usage_events(key, ts);
"""


@dataclass
class ApiKey:
    key: str
    name: str
    rate_per_minute: int
    revoked: bool
    created_at: str


def _db_path(project_dir: Path) -> Path:
    d = project_dir / ".perfectrag"
    d.mkdir(parents=True, exist_ok=True)
    return d / "api_keys.db"


def _conn(project_dir: Path) -> sqlite3.Connection:
    c = sqlite3.connect(str(_db_path(project_dir)))
    c.executescript(SCHEMA)
    c.row_factory = sqlite3.Row
    return c


def issue(project_dir: Path, name: str, rate_per_minute: int = 60) -> ApiKey:
    key = f"sk-rag-{secrets.token_urlsafe(24)}"
    with _conn(project_dir) as c:
        c.execute(
            "INSERT INTO api_keys (key, name, rate_per_minute) VALUES (?, ?, ?)",
            (key, name, rate_per_minute),
        )
    return lookup(project_dir, key)  # type: ignore[return-value]


def lookup(project_dir: Path, key: str) -> ApiKey | None:
    with _conn(project_dir) as c:
        row = c.execute("SELECT * FROM api_keys WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    return ApiKey(
        key=row["key"],
        name=row["name"] or "",
        rate_per_minute=row["rate_per_minute"] or 60,
        revoked=bool(row["revoked"]),
        created_at=row["created_at"] or "",
    )


def list_all(project_dir: Path) -> list[ApiKey]:
    with _conn(project_dir) as c:
        rows = c.execute("SELECT * FROM api_keys ORDER BY created_at DESC").fetchall()
    return [
        ApiKey(
            key=r["key"], name=r["name"] or "",
            rate_per_minute=r["rate_per_minute"] or 60,
            revoked=bool(r["revoked"]), created_at=r["created_at"] or "",
        ) for r in rows
    ]


def revoke(project_dir: Path, key: str) -> bool:
    with _conn(project_dir) as c:
        cur = c.execute("UPDATE api_keys SET revoked=1 WHERE key = ?", (key,))
        return cur.rowcount > 0


def record_usage(project_dir: Path, key: str, endpoint: str, status: int, tokens: int = 0) -> None:
    with _conn(project_dir) as c:
        c.execute(
            "INSERT INTO usage_events (key, endpoint, status, tokens) VALUES (?, ?, ?, ?)",
            (key, endpoint, status, tokens),
        )


def check_rate_limit(project_dir: Path, key: str, rate_per_minute: int) -> bool:
    """Return True if request is allowed; False if over limit."""
    with _conn(project_dir) as c:
        row = c.execute(
            "SELECT COUNT(*) as n FROM usage_events WHERE key = ? "
            "AND ts >= datetime('now', '-1 minute')",
            (key,),
        ).fetchone()
    return (row["n"] or 0) < rate_per_minute


def usage_summary(project_dir: Path, key: str) -> dict:
    with _conn(project_dir) as c:
        today = c.execute(
            "SELECT COUNT(*) as n, COALESCE(SUM(tokens),0) as t FROM usage_events "
            "WHERE key = ? AND date(ts) = date('now')",
            (key,),
        ).fetchone()
        all_time = c.execute(
            "SELECT COUNT(*) as n, COALESCE(SUM(tokens),0) as t FROM usage_events WHERE key = ?",
            (key,),
        ).fetchone()
    return {
        "requests_today": today["n"] or 0,
        "tokens_today": today["t"] or 0,
        "requests_total": all_time["n"] or 0,
        "tokens_total": all_time["t"] or 0,
    }
