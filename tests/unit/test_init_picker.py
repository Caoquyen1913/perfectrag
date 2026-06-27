"""Tests for the init template picker (cold-start chooser)."""

from __future__ import annotations

from perfectrag.cli import _template_choices
from perfectrag.scaffolder import available_templates


def test_recommended_is_first():
    choices = _template_choices("ragflow-stack")
    assert choices[0][0] == "ragflow-stack"
    assert "✓" in choices[0][1]


def test_all_templates_present_once():
    default = "custom-naive-rag"
    values = [v for v, _ in _template_choices(default)]
    avail = set(available_templates())
    assert set(values) == avail              # every template offered
    assert len(values) == len(set(values))   # no duplicates
    assert values[0] == default              # recommended pinned first


def test_labels_include_descriptions():
    choices = _template_choices("code-graph-rag")
    label = dict(choices)["code-graph-rag"]
    assert "—" in label  # "name — description"
