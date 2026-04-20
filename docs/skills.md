# Skills

Skills = domain-specific instructions (prompts, retrieval params) cho RAG service. Format mirror Claude Code's skill format.

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

Copies skeleton vào `skills/<name>/` trong project. Tự viết skill của bạn → tạo `skills/<tên>/SKILL.md` thủ công.

## Mount point

Tất cả templates mount `./skills` read-only vào container (path tuỳ backbone):
- `ragflow-stack`: `/ragflow/skills`
- `lightrag-stack`: `/app/skills`
- `dify-stack`: `/app/skills`
- `custom-naive-rag`: `/app/skills`

Backbone/UI hiện chưa auto-discover skills từ disk — user dán nội dung `SKILL.md` vào system prompt khi tạo Agent/Assistant, hoặc customize template để đọc skills tự động.
