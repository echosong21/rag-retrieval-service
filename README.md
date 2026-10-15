# rag-service

A retrieval-augmented generation (RAG) service over a legal-domain corpus:
semantic retrieval from a vector store, grounded answer generation, and
built-in observability for every query.

> Retrieval quality is treated as a first-class engineering concern here:
> every query is traced, scored and costed, so parameter changes can be
> justified with data rather than intuition.

---

## 1. Features

- **Layered retrieval** over a multi-form legal corpus (statutes, Q&A pairs,
  consultation dialogues, structured judgment records).
- **Grounded generation** — the model answers only from retrieved material and
  explicitly replies with "not mentioned in the material" when nothing matches.
- **Tunable retrieval** — `top_k` and a similarity threshold are injectable at
  runtime (CLI flags), with no code change required.
- **Observability by default** — per-query traces with stage-level latency
  decomposition, token usage, cost estimation, retrieval score distribution and
  failure capture.
- **CI-ready** — lint and test jobs run on every push; tests are
  environment-independent (no network, no real credentials).

## 2. Architecture

```
                ┌──────────────────────────────────────────────┐
  question ───► │  embed (embedding model)                     │
                │        │                                     │
                │        ▼                                     │
                │  search (Milvus, cosine similarity, top-k)   │
                │        │                                     │
                │        ▼                                     │
                │  threshold filter (min_score)                │
                │        │                                     │
                │        ▼                                     │
                │  generate (chat model + grounded prompt)     │
                └────────┬─────────────────────────────────────┘
                         │
                         ▼
              answer + contexts + trace (JSONL) + log file
```

Module layout:

| Path | Responsibility |
|---|---|
| `config/settings.py` | Explicit-path `.env` loading + startup validation (fail fast on missing keys) |
| `src/pipeline.py` | Retrieval pipeline: embed → search → filter → generate |
| `src/observe.py` | Logging setup, trace records, cost estimation, retrieval span |
| `tests/` | Unit tests for configuration loading and validation |
| `experiments/` | Parameter-tuning experiment notes and collected results |
| `.github/workflows/ci.yml` | Lint + test workflow |

## 3. Quick start

```bash
git clone <repository-url>
cd rag-service
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then fill in your own values
```

A vector store must be reachable and populated before querying (see
`MILVUS_URL` below). Verify configuration and run a query:

```bash
python config/settings.py                      # startup validation
python src/pipeline.py -q "your question" --top-k 5 --min-score 0.65
```

## 4. Configuration

All configuration is read from `.env` (see `.env.example` for the full key list).
The service validates every required key at startup and fails immediately with
the missing key name.

| Variable | Purpose |
|---|---|
| `API_KEY` | API credential for the model provider |
| `BASE_URL` | Chat-completions endpoint |
| `MODEL` | Chat model identifier |
| `EMBED_BASE_URL` | Embedding endpoint |
| `EMBED_MODEL` | Embedding model identifier (must match the model used to build the index) |
| `MILVUS_URL` | Vector store endpoint (including scheme, e.g. `http://host:19530`) |

> **Note on embedding consistency:** the query-side embedding model must be
> identical to the one used when the index was built. A mismatch produces
> near-random results with sharply lower similarity scores.

## 5. Corpus

The index behind the measured results contains ~22,900 chunks drawn from a
legal-domain corpus with several complementary data forms:

| Form | Role in answering a question |
|---|---|
| Statutes / long documents | The legal basis — exact article wording |
| Q&A pairs | The direct, short-form answer |
| Consultation dialogues | How users actually phrase the question (colloquial) |
| Structured judgment records | Judicial practice — how courts rule |

Each form is retrieved for a different aspect of the same question, which makes
cross-form recall the natural evaluation target.

## 6. Evaluation and experiments

Retrieval quality is measured with two levels of evidence:

- **Objective (implemented):** similarity score distribution per query
  (`top1`, `avg`, `min`, `n_kept`) recorded automatically in `logs/traces.jsonl`.
- **Subjective (planned):** LLM-as-a-judge relevance scoring, added later.

Experiment design and collected results live in
[`experiments/tuning_notes.md`](experiments/tuning_notes.md). Two parameter
sweeps were run over a fixed question set:

| Sweep | Variable | Headline finding |
|---|---|---|
| 1 | `top_k` ∈ {3, 8} | Changing `top_k` does not change the best hit; it only dilutes context and roughly doubles cost |
| 2 | `min_score` ∈ {0.0, 0.65, 0.70} | A global threshold is unsafe for structured forms: 0.70 removes every structured-data hit |

**Takeaway:** neither knob improves retrieval quality — they only control how
much context reaches the model. Improving recall requires changing the
retrieval strategy itself (multi-route retrieval per data form).

## 7. Observability

Every query produces one JSONL trace record and one log line:

| Field | Meaning |
|---|---|
| `trace_id` | Correlates the log line, the trace record and any stack trace |
| `stage_ms` | Latency breakdown per stage (embed / search / generate) |
| `usage` | Token counts from the model response |
| `cost_cny` | Estimated cost for the query |
| `retrieval` | Score distribution and matched data forms |
| `status` / `error` | Success or failure, with the error captured for reproduction |

Artifacts are written under `logs/` (excluded from version control).

## 8. Known limitations

- The vector store is an external dependency; queries fail cleanly (and are
  traced) when it is unreachable.
- Estimated cost uses a configured unit price and should be reconciled against
  the provider's billing console.
- Cross-form recall is currently limited: a single retrieval route tends to
  return chunks from one data form only. Multi-route retrieval is the next step.
- Retrieval score thresholds are global; per-form thresholds are not yet
  implemented.
- No online demo or container packaging yet.

---

## Development

```bash
pytest -q                 # unit tests (no network required)
python -m compileall .    # syntax check used by CI lint job
```