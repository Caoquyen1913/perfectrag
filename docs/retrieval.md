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

## Cache-Augmented Generation (CAG) — when to skip retrieval

For a **small and stable** corpus, retrieval is overhead: you can load the whole
corpus into the model's context once and answer from it directly (CAG). It wins
when the corpus is small, shared, and broadly queried; RAG wins when it's large,
fresh, per-tenant, or citation-heavy. The wizard flags `extras.cag_candidate`
when your corpus is `small` + `static`.

A practical setup is a **router**: CAG hot-path for the stable core, RAG cold-path
for everything else. perfectRAG recommends CAG (doesn't force it) — a long-context
model + a system prompt holding the corpus is often all you need for tiny corpora.

## Auto-tune — measure, don't guess

The wizard picks retrieval techniques from rule-based defaults — but the *only* way
to know what works on **your** data is to measure it. `perfectrag tune` ingests your
corpus under each technique, scores them against your golden questions, and picks
the empirical winner (highest recall@k / MRR / nDCG, cheapest on ties):

```bash
perfectrag tune --docs ./docs --golden ./golden.jsonl --apply
```

```
 Tune results — best first (k=3)
 #  Config            recall@3  MRR    nDCG@3  LLM cost
 1  baseline ✓        1.000     1.000  1.000   free
 2  parent-doc        1.000     1.000  1.000   free
 3  query-expansion   1.000     1.000  1.000   /query
 4  contextual        1.000     0.875  0.908   /chunk
 5  crag              1.000     0.833  0.875   /query
 Winner: baseline → baseline (no extra technique)
```

Notes:
- The base `perfectrag.yml` provides the store/embedding/LLM; tune only varies the
  retrieval technique (one embedder/LLM is reused across trials, so it's stable).
- `--apply` writes the winning flags into the config (and removes any it didn't pick).
- If no LLM is configured, the LLM-based trials (contextual/query-expansion/CRAG) are
  skipped and baseline/parent-doc still run.
- The example above is a real run: on an easy corpus the LLM techniques *lowered*
  ranking quality (a weak 0.5B model wrote noisy context), so tune correctly chose
  baseline — something rule-based defaults would have gotten wrong.

## Evaluating retrieval

Measure retrieval quality separately from generation with a golden set:

```bash
# golden.jsonl: {"question": "...", "relevant": ["source1.md", ...]}
perfectrag eval --retrieval -d golden.jsonl --k 5 --gate
```

Reports recall@k / MRR / nDCG and (with `--gate`) exits non-zero when
recall@k < 0.8 or MRR < 0.7 — a CI quality gate with no Docker. Generation
metrics (faithfulness, answer relevancy) come from the `eval` addon (RAGAS/DeepEval).
