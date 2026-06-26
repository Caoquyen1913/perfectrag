"""Tests for RAG-access API keys (project SQLite)."""

from __future__ import annotations

from perfectrag import api_keys


def test_issue_and_lookup(tmp_path):
    k = api_keys.issue(tmp_path, "test", rate_per_minute=60)
    assert k.key.startswith("sk-rag-")
    found = api_keys.lookup(tmp_path, k.key)
    assert found is not None
    assert found.name == "test"


def test_revoke(tmp_path):
    k = api_keys.issue(tmp_path, "x")
    assert api_keys.revoke(tmp_path, k.key) is True
    found = api_keys.lookup(tmp_path, k.key)
    assert found is not None
    assert found.revoked is True


def test_list_all(tmp_path):
    api_keys.issue(tmp_path, "a")
    api_keys.issue(tmp_path, "b")
    rows = api_keys.list_all(tmp_path)
    assert len(rows) == 2
    assert {r.name for r in rows} == {"a", "b"}


def test_rate_limit(tmp_path):
    k = api_keys.issue(tmp_path, "x", rate_per_minute=2)
    assert api_keys.check_rate_limit(tmp_path, k.key, 2) is True
    api_keys.record_usage(tmp_path, k.key, "/v1/query", 200)
    api_keys.record_usage(tmp_path, k.key, "/v1/query", 200)
    # 2 requests in the last minute hits the limit
    assert api_keys.check_rate_limit(tmp_path, k.key, 2) is False


def test_usage_summary(tmp_path):
    k = api_keys.issue(tmp_path, "x")
    for _ in range(3):
        api_keys.record_usage(tmp_path, k.key, "/v1/query", 200, tokens=10)
    s = api_keys.usage_summary(tmp_path, k.key)
    assert s["requests_today"] == 3
    assert s["tokens_today"] == 30
