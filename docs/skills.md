# Skills

Skills = domain-specific instructions (prompts, retrieval params) for the RAG service. The format mirrors Claude Code's skill format.

## Structure

```
skills/
  <skill-name>/
    SKILL.md      # YAML frontmatter + body
    (optional) reference/  # supplementary docs
```

`SKILL.md`:

```markdown
---
name: legal-rag
description: Retrieval prompts tuned for legal documents
---
# Instructions body
...
```

## Bundled skills

| Name | Description |
|---|---|
| `legal-rag` | Citations, § sections, no legal advice |
| `code-rag` | Symbol grounding, file:line refs, hybrid search |
| `medical-rag` | Disclaimers, evidence levels |
| `research-rag` | Multi-paper synthesis, citation-per-bullet |

## Add to project

```bash
perfectrag add skill legal-rag --project .
```

Copies a skeleton into `skills/<name>/` in the project. To write your own skill, create `skills/<name>/SKILL.md` manually.

## Mount point

All templates mount `./skills` read-only into the container (path depends on the backbone):
- `ragflow-stack`: `/ragflow/skills`
- `lightrag-stack`: `/app/skills`
- `dify-stack`: `/app/skills`
- `custom-naive-rag`: `/app/skills`

The backbone/UI doesn't auto-discover skills from disk yet — paste the contents of `SKILL.md` into the system prompt when creating an Agent/Assistant, or customize the template to read skills automatically.
