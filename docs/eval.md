# Eval

Measure RAG quality via the `eval` addon. Ships RAGAS (default) + DeepEval (opt-in).

## Setup

```bash
perfectrag init my-rag --with eval
cd my-rag && perfectrag up
```

## Running

Put your dataset in `eval/datasets/<name>.jsonl`. One record per line:

```json
{"question": "What is RAG?", "ground_truth": "Retrieval-augmented generation..."}
```

Run eval:

```bash
perfectrag eval --dataset sample-qa.jsonl
perfectrag eval --dataset my-qa.jsonl --tier deepeval
```

View report: `http://localhost:8081`.

## Metrics (RAGAS tier)

| Metric | What it measures |
|---|---|
| faithfulness | Answer grounded in retrieved context? |
| answer_relevancy | Answer addresses the question? |
| context_precision | Top-k retrieved contexts are actually relevant? |
| context_recall | Ground truth found in retrieved contexts? |

## Custom RAG endpoints

The eval runner POSTs to `${RAG_API_URL}/query` expecting `{answer, sources: [{text}]}`.
Override in `compose.eval.yml` or set `RAG_API_URL` in `.env`.
