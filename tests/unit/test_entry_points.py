"""Test template marketplace via entry_points discovery."""

from __future__ import annotations

from perfectrag import scaffolder


def test_builtin_templates_always_present():
    t = scaffolder.available_templates()
    assert "custom-naive-rag" in t
    assert "ragflow-stack" in t


def test_third_party_discovered_via_entry_points(monkeypatch, tmp_path):
    # Create a fake template dir on disk
    fake_template = tmp_path / "my-plugin-template"
    fake_template.mkdir()
    (fake_template / "copier.yml").write_text("_templates_suffix: .jinja\n")

    class FakeEP:
        def __init__(self, name, provider):
            self.name = name
            self._provider = provider
        def load(self):
            return self._provider

    def provider():
        return {"path": fake_template, "description": "Plugin test"}

    monkeypatch.setattr(
        scaffolder,
        "_third_party_templates",
        lambda: {"plugin-test": {"path": fake_template, "description": "Plugin test"}},
    )
    t = scaffolder.available_templates()
    assert t.get("plugin-test") == "Plugin test"
    assert scaffolder.template_path("plugin-test") == fake_template


def test_builtin_shadows_third_party(monkeypatch, tmp_path):
    """Third-party cannot override a built-in name."""
    bogus = tmp_path / "bogus"
    bogus.mkdir()
    monkeypatch.setattr(
        scaffolder,
        "_third_party_templates",
        lambda: {"custom-naive-rag": {"path": bogus, "description": "Evil"}},
    )
    t = scaffolder.available_templates()
    # Description should be built-in's, not "Evil"
    assert "Evil" not in t["custom-naive-rag"]
