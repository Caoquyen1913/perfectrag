"""Unit tests for bundled skills + add_skill_to_project."""

from __future__ import annotations

import pytest

from perfectrag import skills


def test_bundled_skills_present():
    bundled = skills.list_bundled_skills()
    assert "legal-rag" in bundled
    assert "code-rag" in bundled
    assert all(desc for desc in bundled.values()), bundled


def test_add_skill_copies_files(tmp_path):
    skills.add_skill_to_project("legal-rag", tmp_path)
    skill_md = tmp_path / "skills" / "legal-rag" / "SKILL.md"
    assert skill_md.exists()
    content = skill_md.read_text(encoding="utf-8")
    assert content.startswith("---")
    assert "name: legal-rag" in content


def test_add_unknown_skill_raises(tmp_path):
    with pytest.raises(KeyError):
        skills.add_skill_to_project("does-not-exist", tmp_path)
