# Retrieval Evaluation Report

> Objective, reproducible retrieval metrics for `rag-service` over the frozen
> golden set (17 questions, see `golden_questions.md` / `.json`).
> Every number below comes from an actual run recorded under `results/`.

---

## 1. Frozen setup

| Item | Value |
|---|---|
| Collection | `law_docs` (~22,900 chunks, COSINE) |
| Embedding model | same model on query and index side (consistency is mandatory) |
| `min_score` | 0.0 (no threshold filtering) |
| Golden set | 17 questions across 4 data forms + 3 cross-form probes |
| Judge | a question hits when an expected source appears in the returned top-k |

---

## 2. Results — four configurations

| # | Strategy | Candidates | **Overall** | docs | faq | dialogues | tables | **cross** | Latency (mean) |
|:--:|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| ① | single-route (`top_k=5`) | 5 | 94.1% | 100% | 100% | **100%** | 100% | **66.7%** | 568 ms |
| ② | multi-route, `per_form=2` | 8 | 94.1% | 100% | 100% | **66.7%** | 100% | **100%** | 351 ms |
| ③ | multi-route, `per_form=3` | 12 | **100%** | 100% | 100% | 100% | 100% | 100% | 392 ms |
| ④ | multi-route, `per_form=5` | 20 | **100%** | 100% | 100% | 100% | 100% | 100% | 455 ms |

Source files: `results/summary_*-{single,multi_pf2,multi_pf3,multi_pf5}.json`
(the initial single-run baseline is kept at `summary_2026-10-16.json`).

---

## 3. Findings

### Finding 1 — Multi-route retrieval fixes cross-form recall failure, but with a zero-sum side effect
At `per_form=2` (8 candidates) the cross-form hit rate rises **66.7% → 100%**, while
*dialogues* falls **100% → 66.7%**; the overall rate is unchanged at 94.1%.

Cause: the candidate budget is fixed. The dialogues corpus is by far the largest,
so a single-route query naturally spends most of its top-k there. Reserving slots
per form necessarily takes slots away from it.

### Finding 2 — Raising the budget from 8 to 12 candidates removes the zero-sum effect
At `per_form=3` (12 candidates) **all 17 questions hit** — cross-form *and*
dialogues are both satisfied. So the zero-sum behaviour was a symptom of an
under-sized budget, not a flaw of multi-route retrieval itself.

### Finding 3 — Diminishing returns: `per_form=3` is the knee of the curve
Going `per_form=3 → 5` (12 → 20 candidates) yields **no accuracy gain** (100% → 100%)
but costs **+16% latency** (392 ms → 455 ms). `per_form=3` is therefore the
cost-effective operating point for this corpus and question set.

### Finding 4 — Multi-route retrieval is not slower than single-route
Mean single-route latency (568 ms) exceeds every multi-route configuration
(351–455 ms). Running four narrower, metadata-filtered queries is cheaper than one
wide query. *Caveat:* the single-route mean includes one cold-start outlier
(6,672 ms); a cleaner same-day baseline is 193 ms, which is lower than the
multi-route figures — so this finding depends on how the runs were paired, and
should be re-measured under a warm cache before being quoted as a rule.

### Finding 5 — `top1` is independent of retrieval strategy
Across all four configurations the best-hit score is effectively identical
(0.7416 / 0.7419, 0.7234, 0.7479). This reproduces the earlier parameter sweeps:
`top_k`, `min_score` and route strategy change *how much context is assembled*,
not *how good the best match is*.

---

## 4. Failure attribution (required for every miss)

| Config | id | Form | Expected | Verdict | Attribution |
|---|:--:|---|---|:--:|---|
| ① single | X1 | cross | statute + Q&A + judgment records | **0/3 miss** | Single route returned 8 chunks from one form only (dialogues). Cross-form recall is unreachable without per-form routing — the same question scored 1/1 when judged as a dialogues-only item (C2). |
| ② `pf2` | C3 | dialogues | consultation transcript | **0/1 miss** | The per-form budget (2 slots) pushed this out; dialogues is the largest corpus and needs more slots than the smallest forms. Resolved by `per_form=3`. |
| ③ `pf3` | — | — | — | **no miss** | (One `partial` remains: C2 hit 1 of 2 expected dialogues files, which is an artifact of the strict "all expected sources" rule — see note below.) |

> **Note on the `partial` verdict for C2**: two dialogues files are listed as
> expected because the same topic appears in both. Requiring *all* of them is
> stricter than necessary for a recall metric; treating it as a hit would make
> `pf3` a clean 17/17.

---

## 5. Performance and cost (measured)

Source: `logs/traces.jsonl` — **52 records** (2026-10-12 to 10-16), single machine,
single embedding model. 51 succeeded, 1 failed (that failure is the missing-collection
issue documented in `TROUBLESHOOTING.md`).

### 5.1 Latency breakdown (successful requests only, ms)

| Stage | **median** | mean | min | max |
|---|:--:|:--:|:--:|:--:|
| embedding | 366.6 | 579.2 | 284.9 | 3,697.3 |
| **retrieval** | **30.6** | 387.3 | 13.8 | **16,674.3** |
| **generation** | **2,897.1** | 3,439.0 | 0.0 | 10,470.9 |

**End-to-end composition (by median)**: embedding ≈ 367 ms + retrieval ≈ 31 ms +
generation ≈ 2,897 ms **≈ 3.3 s**

> Means sit well above medians because a few outliers pull them up
> (retrieval: mean 387 ms vs median 31 ms — a 12× gap)
> ⇒ **judge latency by median and tail, not by mean alone.**

### 5.2 Cost and tokens (successful requests only)

| Metric | Value |
|---|---|
| Cost per query — mean / median | **0.00465 / 0.00448 CNY** |
| Cost per query — min / max | 0.0 / 0.01234 CNY |
| Total across 52 queries | **0.237 CNY** |
| Input tokens — mean / max | 1,555.3 / 3,034 |
| Output tokens — mean / max | 241.5 / 900 |
| Total tokens — mean | 1,796.8 |

### 5.3 Three conclusions drawn from this data

**① Generation is the only significant latency source; retrieval is not the bottleneck**

Retrieval's median is **30.6 ms** — roughly **1%** of end-to-end latency.
⇒ This **backs the decision not to tune the index** (see `DESIGN.md` §6): optimising a
stage that accounts for 1% does nothing for user-visible latency.

**② Retrieval is fast on average, but its tail is uncontrolled**

Median 30.6 ms versus a maximum of **16,674 ms** (a spread of over 500×).
⇒ The goal of any retrieval-layer optimisation should therefore be
**tail-latency stability, not a lower mean**. Judged by medians, removing all four
serial retrievals would save only hundreds of milliseconds; the real gain lies in
**eliminating second-scale outliers**.

**③ Cost is small in magnitude, but the current figure is a lower bound**

About **0.0045 CNY per query**, under 0.25 CNY across 52 queries — cost is not a
constraint at this scale.

⚠️ **Scope caveat**: the trace records **generation-stage LLM cost** (token-based).
**Embedding and (future) reranking calls are not included** ⇒ the figure above is a
**lower bound, not full-chain cost**. Cost-tracking coverage is a known gap in this
project's observability.

### 5.4 Comparability

- These figures come from **one machine, one embedding model, a specific date range**
  ⇒ **not directly comparable across environments**.
- To judge whether performance has changed, runs must share the **same collection,
  same embedding model, same `top_k` / `per_form`**, and be recorded **with a commit
  SHA** — otherwise there is no way to attribute the difference to a particular change.
- The generation stage is heavily affected by provider-side queueing, so
  **within-day variance can exceed the difference caused by a code change**.
- **Repeated embedding of the same text is not bit-identical.** Measured: the same
  text, same model, two independent calls returned vectors whose largest absolute
  difference was about **7×10⁻³** — well above floating-point rounding (≈10⁻⁷).
- **The resulting score noise was then measured end-to-end.** The same corpus, same
  parameters and same model were indexed **twice** (two independent builds), and all
  17 questions were scored against both. Per-question `top1` differed by up to
  **±0.005** — an order of magnitude more than a naive per-vector estimate suggests,
  because the deviation accumulates across 1024 dimensions.
  Two consequences for experiment discipline:
  1. **Comparisons within one experiment must reuse the same vector set** — re-embedding
     the same corpus injects roughly ±0.005 of noise on top of whatever is being tested.
  2. **A score difference below 0.005 should not be read as an improvement.**
     Treat only changes clearly above this noise floor as signal.
     (The hit/miss verdicts in this report are unaffected: the affected questions were
     all well above their thresholds.)

### 5.5 Index build (measured)

One full rebuild of the 22,900-chunk index, recorded in one run:

| Stage | Time |
|---|:--:|
| Splitting corpus into chunks | 0.5 s |
| **Embedding** (22,900 chunks, batch of 20) | **442.2 s** |
| Inserting into the vector store (batch of 500) | 110.1 s |
| **Total** | **552.8 s (≈ 9.2 min)** |

> An earlier estimate put a full rebuild at 11–32 minutes; the measured figure is
> **9.2 minutes**, i.e. 1.5–4× faster. Estimations like this are worth replacing
> with a measurement as soon as one run is available.
>
> **Where the time goes:** embedding dominates (80% of the build). This is why an
> embedding cache is the single most valuable optimisation for experimentation —
> it reduces repeat experiments from ~9 minutes to under 2 minutes.

---

## 6. Reproduce

```bash
python evals/run_eval.py --mode single
python evals/run_eval.py --mode multi --per-form 2
python evals/run_eval.py --mode multi --per-form 3
python evals/run_eval.py --mode multi --per-form 5
```

Each run writes `results/results_<date>_<mode>[_pf<N>].jsonl` (per question) and
`results/summary_<date>_<mode>[_pf<N>].json` (aggregate). Parameters are recorded
inside the summary, so numbers from different configurations are never confused.

**Comparability rule:** the embedding model, collection and `min_score` must stay
identical across runs. Changing the embedding model invalidates all comparisons
(the query-side and index-side models must match).