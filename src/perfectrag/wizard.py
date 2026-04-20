"""Interactive wizard: conditional prompts that produce an `Answers` object."""

from __future__ import annotations

from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from perfectrag.recipes import Answers


def run_wizard() -> Answers:
    use_case = inquirer.select(
        message="Use-case chính của RAG service này?",
        choices=[
            Choice("qa_docs", name="Q&A trên tài liệu (PDF / Markdown / docs)"),
            Choice("graphrag", name="GraphRAG — multi-hop reasoning, knowledge graph"),
            Choice("multimodal", name="Multimodal — text + images + tables"),
            Choice("code_rag", name="Code search / code RAG"),
            Choice("agent_workflow", name="Agent / workflow with tool calling"),
        ],
        default="qa_docs",
    ).execute()

    modality = inquirer.checkbox(
        message="Loại dữ liệu trong corpus? (space to toggle, enter to confirm)",
        choices=[
            Choice("text", name="Text thuần", enabled=True),
            Choice("tables", name="Bảng (PDF có table)"),
            Choice("images", name="Hình ảnh / scanned docs"),
            Choice("code", name="Source code"),
        ],
    ).execute()

    privacy = inquirer.select(
        message="Yêu cầu privacy?",
        choices=[
            Choice("fully_local", name="Fully local (không gọi API cloud nào)"),
            Choice("hybrid_api", name="Hybrid — có thể dùng API cloud cho LLM lớn"),
        ],
        default="fully_local",
    ).execute()

    multi_hop = False
    if use_case != "graphrag":
        multi_hop = inquirer.confirm(
            message="Câu hỏi thường cần multi-hop reasoning (suy luận qua nhiều tài liệu)?",
            default=False,
        ).execute()

    corpus_size = inquirer.select(
        message="Corpus size dự kiến?",
        choices=[
            Choice("small", name="Nhỏ (<10k docs)"),
            Choice("medium", name="Vừa (10k - 1M docs)"),
            Choice("large", name="Lớn (>1M docs)"),
        ],
        default="small",
    ).execute()

    user_scale = inquirer.select(
        message="Số lượng user đồng thời?",
        choices=[
            Choice("solo", name="Solo dev / cá nhân"),
            Choice("team", name="Team (<10 users)"),
            Choice("production", name="Production (nhiều user, cần SLA)"),
        ],
        default="solo",
    ).execute()

    return Answers(
        use_case=use_case,
        modality=modality or ["text"],
        privacy=privacy,
        multi_hop=multi_hop,
        corpus_size=corpus_size,
        user_scale=user_scale,
    )
