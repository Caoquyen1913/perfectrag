"""RAG eval runner. Invoked via `docker compose run --rm eval python runner.py ...`.

Reads a JSONL dataset where each line is: {"question": str, "ground_truth": str}.
Queries the RAG API for each, scores with RAGAS, writes HTML report to /app/reports.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import httpx
import pandas as pd

RAG_API_URL = os.environ["RAG_API_URL"]
REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", "/app/reports"))


def query_rag(question: str) -> tuple[str, list[str]]:
    with httpx.Client(timeout=60) as client:
        r = client.post(f"{RAG_API_URL}/query", json={"question": question})
        r.raise_for_status()
        data = r.json()
    answer = data.get("answer", "")
    contexts = [s.get("text", "") for s in data.get("sources", []) if isinstance(s, dict)]
    # Fallback: custom-naive-rag returns source metadata only — pull text from `answer` if needed
    return answer, contexts


def run_ragas(records: list[dict]) -> pd.DataFrame:
    """Score with RAGAS. Lazy import so missing deps don't break the container start."""
    from datasets import Dataset
    from ragas import evaluate
    from ragas.metrics import (
        answer_relevancy,
        context_precision,
        context_recall,
        faithfulness,
    )

    ds = Dataset.from_list([
        {
            "question": r["question"],
            "answer": r["answer"],
            "contexts": r["contexts"] or [""],
            "ground_truth": r.get("ground_truth", ""),
        }
        for r in records
    ])
    result = evaluate(
        ds,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
    )
    return result.to_pandas()


def write_report(df: pd.DataFrame, title: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    path = REPORTS_DIR / f"report-{ts}.html"
    summary = df[[c for c in df.columns if c not in ("question", "answer", "contexts", "ground_truth")]].mean(numeric_only=True)
    html = (
        f"<h1>{title}</h1>"
        f"<p>Generated: {ts}</p>"
        f"<h2>Mean scores</h2>{summary.to_frame('score').to_html()}"
        f"<h2>Per-row</h2>{df.to_html(index=False)}"
    )
    path.write_text(html, encoding="utf-8")
    index = REPORTS_DIR / "index.html"
    index.write_text(html, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, help="Path to JSONL dataset")
    parser.add_argument("--tier", default=os.environ.get("TIER", "ragas"), choices=["ragas", "deepeval"])
    args = parser.parse_args()

    path = Path(args.dataset)
    if not path.exists():
        print(f"Dataset not found: {path}", file=sys.stderr)
        return 2

    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        answer, contexts = query_rag(item["question"])
        records.append({
            **item,
            "answer": answer,
            "contexts": contexts,
        })

    if args.tier == "ragas":
        df = run_ragas(records)
        report = write_report(df, "RAGAS eval")
    else:
        # DeepEval path (structured test cases); minimal wiring — users customize
        df = pd.DataFrame(records)
        report = write_report(df, "DeepEval (raw)")

    print(f"Report: {report}")
    print(df.describe(include="all").to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
