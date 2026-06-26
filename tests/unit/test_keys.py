"""Tests for provider-key storage (~/.perfectrag/keys.yml)."""

from __future__ import annotations

import pytest

from perfectrag import keys


@pytest.fixture
def isolated_keys(tmp_path, monkeypatch):
    fake = tmp_path / ".perfectrag" / "keys.yml"
    monkeypatch.setattr(keys, "KEYS_DIR", tmp_path / ".perfectrag")
    monkeypatch.setattr(keys, "KEYS_FILE", fake)
    return fake


def test_set_and_get(isolated_keys):
    keys.set_key("gemini", "AIza-secret-1")
    assert keys.get_key("gemini") == "AIza-secret-1"


def test_env_overrides_file(isolated_keys, monkeypatch):
    keys.set_key("openai", "sk-file")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    assert keys.get_key("openai") == "sk-env"


def test_remove(isolated_keys):
    keys.set_key("anthropic", "sk-ant-foo")
    assert keys.remove_key("anthropic") is True
    assert keys.get_key("anthropic") is None
    assert keys.remove_key("anthropic") is False


def test_list_keys_masked(isolated_keys):
    keys.set_key("gemini", "AIzaSy-abcdef-longvalue")
    listed = keys.list_keys()
    assert "gemini" in listed
    assert "AIzaSy-abcdef-longvalue" not in listed["gemini"]
    assert listed["gemini"].startswith("AIza")
