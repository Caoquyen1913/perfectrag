"""Tests for /v1/* SaaS Query API — mock the RAG instance."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PERFECTRAG_PROJECT_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(project_dir, monkeypatch):
    from perfectrag import query_api as qa

    # Mock RAG so we don't need models / servers
    class FakeResult:
        answer = "42"
        hits: list = []
        def as_dict(self):
            return {"answer": "42", "sources": []}

    class FakeRAG:
        def query(self, q, k=None):
            return FakeResult()
        def ingest(self, p):
            return 7
        def ingest_text(self, t):
            return 3
        class store:
            @staticmethod
            def list_collections():
                return ["docs"]

    monkeypatch.setattr(qa, "_get_rag", lambda: FakeRAG())
    return TestClient(qa.app)


def test_health_unauthed(client):
    assert client.get("/health").status_code == 200


def test_query_requires_auth(client):
    r = client.post("/v1/query", json={"question": "x"})
    assert r.status_code == 401


def test_query_with_valid_key(client, project_dir):
    from perfectrag import api_keys
    k = api_keys.issue(project_dir, "t", rate_per_minute=100)
    r = client.post("/v1/query", json={"question": "x"},
                    headers={"Authorization": f"Bearer {k.key}"})
    assert r.status_code == 200, r.text
    assert r.json() == {"answer": "42", "sources": []}


def test_revoked_key_rejected(client, project_dir):
    from perfectrag import api_keys
    k = api_keys.issue(project_dir, "t")
    api_keys.revoke(project_dir, k.key)
    r = client.post("/v1/query", json={"question": "x"},
                    headers={"Authorization": f"Bearer {k.key}"})
    assert r.status_code == 401


def test_rate_limit_429(client, project_dir):
    from perfectrag import api_keys
    k = api_keys.issue(project_dir, "t", rate_per_minute=1)
    h = {"Authorization": f"Bearer {k.key}"}
    assert client.post("/v1/query", json={"question": "x"}, headers=h).status_code == 200
    assert client.post("/v1/query", json={"question": "x"}, headers=h).status_code == 429


def test_ingest_text(client, project_dir):
    from perfectrag import api_keys
    k = api_keys.issue(project_dir, "t")
    r = client.post("/v1/ingest", json={"text": "hello world"},
                    headers={"Authorization": f"Bearer {k.key}"})
    assert r.status_code == 200
    assert r.json()["chunks"] == 3


def test_usage_endpoint(client, project_dir):
    from perfectrag import api_keys
    k = api_keys.issue(project_dir, "t")
    h = {"Authorization": f"Bearer {k.key}"}
    client.post("/v1/query", json={"question": "x"}, headers=h)
    r = client.get("/v1/usage", headers=h)
    assert r.status_code == 200
    assert r.json()["requests_today"] >= 1
