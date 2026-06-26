"""Tests for the addon overlay system."""

from __future__ import annotations

import pytest

from perfectrag import addons


def test_registry_has_all_expected_addons():
    expected = {
        "ingest-worker", "eval", "observability", "context-eng",
        "notion-sync", "gdrive-sync", "confluence-sync", "paperclip",
    }
    assert expected.issubset(set(addons.REGISTRY.keys()))


def test_registry_specs_well_formed():
    for name, spec in addons.REGISTRY.items():
        assert spec.name == name
        assert spec.description, name
        assert spec.compose_file.startswith("compose."), name
        assert spec.compose_file.endswith(".yml"), name


def test_state_roundtrip(tmp_path):
    addons.save_state(tmp_path, {"installed": ["eval", "observability"]})
    assert addons.list_installed(tmp_path) == ["eval", "observability"]


def test_add_addon_copies_compose_and_updates_state(tmp_path):
    spec = addons.add_addon_to_project("eval", tmp_path, template_vars={})
    assert spec.name == "eval"
    assert (tmp_path / "compose.eval.yml").exists()
    assert "eval" in addons.list_installed(tmp_path)


def test_compose_args_chains_all_installed(tmp_path):
    addons.add_addon_to_project("eval", tmp_path)
    addons.add_addon_to_project("observability", tmp_path)
    args = addons.compose_args(tmp_path)
    assert args[:2] == ["-f", "docker-compose.yml"]
    assert "compose.eval.yml" in args
    assert "compose.observability.yml" in args


def test_compose_args_skips_missing_files(tmp_path):
    addons.save_state(tmp_path, {"installed": ["eval", "ghost"]})
    # Only compose.eval.yml exists; ghost should be silently skipped
    (tmp_path / "compose.eval.yml").write_text("services: {}")
    args = addons.compose_args(tmp_path)
    assert "compose.eval.yml" in args
    assert "compose.ghost.yml" not in args


def test_unknown_addon_raises(tmp_path):
    with pytest.raises(KeyError):
        addons.add_addon_to_project("does-not-exist", tmp_path)


def test_requires_dependency_check(tmp_path, monkeypatch):
    # Inject a fake spec with a dependency
    fake = addons.AddonSpec(
        name="fake-dep",
        description="test",
        compose_file="compose.fake-dep.yml",
        requires=("eval",),
    )
    monkeypatch.setitem(addons.REGISTRY, "fake-dep", fake)
    with pytest.raises(ValueError, match="requires 'eval'"):
        addons.add_addon_to_project("fake-dep", tmp_path)
