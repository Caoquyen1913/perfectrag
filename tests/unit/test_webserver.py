"""Smoke tests for the FastAPI backend."""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from perfectrag.webserver import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_hw(client):
    r = client.get("/api/hw")
    assert r.status_code == 200
    data = r.json()
    assert "cpu_cores" in data
    assert "tier" in data


def test_templates(client):
    r = client.get("/api/templates")
    assert r.status_code == 200
    assert "custom-naive-rag" in r.json()


def test_addons(client):
    r = client.get("/api/addons")
    assert r.status_code == 200
    names = {a["name"] for a in r.json()}
    assert "eval" in names and "paperclip" in names


def test_recommend(client):
    r = client.post("/api/recommend", json={"use_case": "qa_docs"})
    assert r.status_code == 200
    data = r.json()
    assert data["recipe"]["template"] in {"custom-naive-rag", "ragflow-stack"}


def test_scaffold(client, tmp_path):
    r = client.post("/api/scaffold", json={
        "project_dir": str(tmp_path / "out"),
        "answers": {"use_case": "qa_docs"},
        "addons": ["eval"],
        "force": True,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert "eval" in data["addons_installed"]
    assert (tmp_path / "out" / "compose.eval.yml").exists()


def test_doctor_missing_project(client, tmp_path):
    r = client.get("/api/doctor", params={"project_dir": str(tmp_path / "nope")})
    assert r.status_code == 200
    # First check should FAIL because no compose file
    first = r.json()["checks"][0]
    assert first["status"] == "fail"
