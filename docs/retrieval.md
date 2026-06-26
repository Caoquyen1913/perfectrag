# Advanced retrieval

The embedded library (`perfectrag.core.RAG`) ships several retrieval-quality
techniques. All are off by default and configured in `perfectrag.yml` (or the
`RAG(...)` constructor). The wizard enables sensible ones automatically based on
your answers — see the `extras` it sets.

## Contextual Retrieval (Anthropic)

Prepends a one-sentence, LLM-generated situating context to each chunk **before
embedding**, so a chunk like *"the rate is 4.5%"* becomes findable by *"Q3 loan
rate"*. Cuts retrieval failures substantially; costs one cheap LLM call per chunk
at ingest time.

```yaml
contextual: true
```

Enabled by the wizard for `qa_docs`/`code_rag` on small/medium corpora.

## Parent-document retrieval

Embeds small **child** chunks for precise matching, but feeds the larger
**parent** block to the LLM for context. Free (no extra LLM calls); shared
parents are de-duplicated in the prompt.

```yaml
chunk_size: 512           # child size
parent_chunk_size: 2048   # parent block size (must be > chunk_size)
```

## Query expansion + RRF

Generates N alternate phrasings of the query, retrieves for each, and fuses the
results with **Reciprocal Rank Fusion**. Improves recall on terse or multi-hop
questions; costs one LLM call per query.

```yaml
query_expansion: 3
```

## Corrective RAG (CRAG)

Grades the first retrieval pass with the LLM; if it looks irrelevant, re-retrieves
once with query expansion before answering. Model-agnostic and fails open (never
blocks an answer on grader error).

```yaml
corrective: true
```

Enabled by the wizard when `multi_hop` is true or `priority: accuracy`.

## Putting it together

```yaml
collection: documents
chunk_size: 512
parent_chunk_size: 2048
top_k: 5
contextual: true
query_expansion: 3
corrective: true

store: { name: chroma, path: ./data/chroma }
embedding: { model: BAAI/bge-m3, backend: sentence_transformers }
llm: { runtime: ollama, model: qwen2.5:7b-instruct-q4_K_M }
```

## Evaluating retrieval

Measure retrieval quality separately from generation with a golden set:

```bash
# golden.jsonl: {"question": "...", "relevant": ["source1.md", ...]}
perfectrag eval --retrieval -d golden.jsonl --k 5 --gate
```

Reports recall@k / MRR / nDCG and (with `--gate`) exits non-zero when
recall@k < 0.8 or MRR < 0.7 — a CI quality gate with no Docker. Generation
metrics (faithfulness, answer relevancy) come from the `eval` addon (RAGAS/DeepEval).
