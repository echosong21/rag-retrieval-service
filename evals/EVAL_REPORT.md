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

Source: `logs/traces.jsonl` — **53 records** (2026-10-12 to 10-20), single machine,
single embedding model. 52 succeeded, 1 failed (that failure is the missing-collection
issue documented in `TROUBLESHOOTING.md`).

### 5.1 Latency breakdown (successful requests only, ms)

| Stage | **median** | mean | min | max |
|---|:--:|:--:|:--:|:--:|
| embedding | 364.8 | 574.3 | 284.9 | 3,697.3 |
| **retrieval** | **30.8** | 380.9 | 13.8 | **16,674.3** |
| **generation** | **2,919.1** | 3,436.8 | 0.0 | 10,470.9 |

**End-to-end composition (by median)**: embedding ≈ 365 ms + retrieval ≈ 31 ms +
generation ≈ 2,919 ms **≈ 3.3 s**

> Means sit well above medians because a few outliers pull them up
> (retrieval: mean 387 ms vs median 31 ms — a 12× gap)
> ⇒ **judge latency by median and tail, not by mean alone.**

### 5.2 Cost and tokens (successful requests only)

| Metric | Value |
|---|---|
| Cost per query — mean / median | **0.00473 / 0.00454 CNY** |
| Cost per query — min / max | 0.0 / 0.01234 CNY |
| Total across 52 successful queries | **0.246 CNY** |
| Input tokens — mean / max | 1,596.5 / 3,533 |
| Output tokens — mean / max | 240.8 / 900 |
| Total tokens — mean | 1,837.3 |

### 5.3 Three conclusions drawn from this data

**① Generation is the only significant latency source; retrieval is not the bottleneck**

Retrieval's median is **30.8 ms** — roughly **1%** of end-to-end latency.
⇒ This **backs the decision not to tune the index** (see `DESIGN.md` §6): optimising a
stage that accounts for 1% does nothing for user-visible latency.

**② Retrieval is fast on average, but its tail is uncontrolled**

Median 30.8 ms versus a maximum of **16,674 ms** (a spread of over 500×).
⇒ The goal of any retrieval-layer optimisation should therefore be
**tail-latency stability, not a lower mean**. Judged by medians, removing all four
serial retrievals would save only hundreds of milliseconds; the real gain lies in
**eliminating second-scale outliers**.

**③ Cost is small in magnitude, but the current figure is a lower bound**

About **0.0047 CNY per query**, just under 0.25 CNY across 52 successful queries — cost
is not a constraint at this scale.

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

## 6. Retrieval strategy comparison (2026-10-20)

### 6.1 Configurations

| Config | What it does | Commit |
|---|---|---|
| `multi` (serial) | 4 per-form queries executed **one after another** | `e0c1a0a` |
| **`multi` (concurrent)** | same semantics, queries issued **in parallel** | `5c96557` |
| **`hybrid`** | + a BM25 sparse route, fused with **two-layer RRF** (per-form fusion, then forms ordered by their best vector similarity) | `5c96557` |

All three: 17 questions, `per_form=3`, `min_score=0.0`, same collection and embedding model.

### 6.2 Results

| Metric | `multi` serial (`e0c1a0a`) | `multi` concurrent | `hybrid` |
|---|:--:|:--:|:--:|
| Overall hit rate | 100% | **100%** | **100%** |
| Verdicts | hit 16 / partial 1 | **identical** | hit 17 |
| Candidates per query | 12 | 12 | 20–24 |
| **Top-1 is expected** | — | **70.6%** | 70.6% |
| **MRR** | — | **0.8284** | 0.7737 |
| Latency (mean) | 392 ms | **234.6 ms** | 631.1 ms |

> ⚠️ The 392 ms figure comes from a **different date**, so per §5.4 it is not directly
> comparable. The reliable same-session measurement is the single-query one:
> **concurrent 48.2 ms vs serial 208.8 ms (−76.9%)**, with an **identical result set**.

### 6.3 Same-budget comparison

`hybrid` returns a larger pool (20–24 candidates vs 12), and rank metrics are
**sensitive to pool size**. Truncating both to the same budget `K` is the fair comparison:

| K | `multi` hit / top1 / MRR | `hybrid` hit / top1 / MRR |
|:--:|:--:|:--:|
| **3** | **94.1%** / 70.6% / **0.8170** | 76.5% / 70.6% / 0.7353 |
| **5** | **100.0%** / 70.6% / **0.8317** | 82.4% / 70.6% / 0.7471 |
| 8 | 100.0% / 70.6% / **0.8317** | 100.0% / 70.6% / 0.7737 |
| 12 | 100.0% / 70.6% / 0.8317 | 100.0% / 70.6% / 0.7737 |

### 6.4 Findings

**Finding 6 — Concurrency removes 77% of retrieval latency without changing results.**
Single query: 208.8 ms → 48.2 ms. The per-form hits and the final result set are
**identical** to the serial version, so the optimisation is behaviour-preserving.

**Finding 7 — Hybrid retrieval is not a net win on this corpus.**
It recalls one more source (verdicts `hit 16 / partial 1` → `hit 17`), but at **every
budget** its ranking is worse, and at small budgets it is much worse
(hit rate −17.6 pt at K=3/5). It needs **8+ candidates** to match what plain multi-route
reaches with **5**. It is therefore **disabled by default**.

**Finding 8 — How the two routes are fused matters more than whether they are fused.**
A single-layer RRF over all 8 routes (4 forms × 2 retrievers) **damaged** ranking:
top-1 70.6% → **47.1%**, MRR 0.8284 → **0.6536** (tables questions fell from rank 1 to
ranks 7/8/7). Root cause: RRF gives **every route's rank-1 equal weight**, but the forms
are not equally reliable (tables' best hit scores about 0.55 vs faq's about 0.72).
Splitting into two layers — **per-form fusion** (which keeps the sparse recall
contribution) and then **ordering forms by their best vector similarity** — restores
top-1 to 70.6%.

**Finding 9 — RRF weights did not change the outcome.**
Weighting the dense route (1:1 / 2:1 / 3:1 / 5:1) produced **identical** results
(17/17, 12/17, MRR 0.7737). ⚠️ The cause is **not** "the two routes rank alike":
measured over 68 form-pairs, **0 were in the same order** and the candidate overlap was
only **8%**. The real reason is that dense dominates the **top ranks**, so weighting only
reorders the **tail** — the top-N composition and order stay the same.
⇒ **Reusable rule: weighting helps only when the routes actually compete near the top.**

### 6.5 Methodology note: pick metrics that can see the change

The evaluation originally reported **hit rate only** — "is the expected source anywhere in
the results". A fusion strategy **only changes the order, not the set**, so hit rate is
blind to exactly the thing being tested. Adding **top-1-is-expected** and **MRR** made the
effect visible — and that is what exposed Findings 8 and 9.

Two traps hit along the way, both worth remembering:

1. **Rank metrics are pool-size sensitive** ⇒ truncate to a common budget before comparing.
2. **A difference computed across two different scenarios is not a unit cost.** Both
   "which route is better" and "how many tokens per chunk" were once mis-attributed by
   reasoning from deltas instead of from controlled measurements.

---

## 7. Index parameters: no measurable difference (2026-10-21)

### 7.1 What was compared

Four indexes built over the **same vectors and the same chunking** (22,900 chunks,
identical embedding model), plus the original collection as a reference:

| Collection | Index | Commit |
|---|---|---|
| `law_docs` | (original, server default) | — |
| `law_docs_idx_default` | server default | `887aa03` |
| `law_docs_idx_hnsw16` | HNSW, `M=16`, `efConstruction=200` | `887aa03` |
| `law_docs_idx_hnsw32` | HNSW, `M=32`, `efConstruction=400` | `887aa03` |
| `law_docs_idx_ivf` | IVF_FLAT, `nlist=128` | `887aa03` |

### 7.2 Retrieval quality: **identical**

| Index | Hit rate | Top-1 is expected | MRR |
|---|:--:|:--:|:--:|
| default | 100% | 70.6% | 0.8382 |
| HNSW M=16 | 100% | 70.6% | 0.8382 |
| HNSW M=32 | 100% | 70.6% | 0.8382 |
| IVF_FLAT | 100% | 70.6% | 0.8382 |

All four configurations return the **same candidate sets** — the metrics are identical
to the last digit. **There is no measurable quality difference between these indexes
at this scale.**

### 7.3 Retrieval latency: the difference does **not** survive repetition

**Method** (this is the part that matters):

- **Retrieval only** — query vectors were embedded once and reused; the embedding cost
  (150–200 ms) is common to all variants and would have swamped the signal.
- **85 measured searches per collection** (17 questions × 5 rounds), after a warm-up
  pass, since the first searches carry one-off initialisation cost.
- **The whole benchmark was run twice** — and that is what settled the question.

**Run 1**

| Collection | p50 | p90 | p95 | max |
|---|:--:|:--:|:--:|:--:|
| `law_docs` | **17.5** | 47.8 | 54.5 | 139.8 |
| `idx_default` | **18.5** | 68.8 | 109.0 | 277.2 |
| `idx_hnsw16` | 18.2 | 63.9 | 84.2 | 312.3 |
| `idx_hnsw32` | 17.7 | 51.8 | 62.7 | 160.1 |
| `idx_ivf` | **17.4** | 48.4 | 56.9 | 286.7 |

**Run 2**

| Collection | p50 | p90 | p95 | max |
|---|:--:|:--:|:--:|:--:|
| `law_docs` | **19.4** | 77.3 | 104.3 | 309.8 |
| `idx_default` | **17.4** | 51.9 | 65.2 | 317.8 |
| `idx_hnsw16` | 18.5 | 81.4 | 114.4 | 316.3 |
| `idx_hnsw32` | 17.5 | 38.3 | 49.1 | 308.2 |
| `idx_ivf` | 17.5 | 47.5 | 68.9 | 128.5 |

**⇒ The ranking reversed between the two runs.** In run 1 the fastest was `idx_ivf`
(17.4 ms) and the slowest `idx_default` (18.5 ms); in run 2 those two swapped
(the fastest became `idx_default`, and `law_docs` became the slowest at 19.4 ms).

- **Spread between indexes: 1.1–2.0 ms.**
- **Spread of the *same* index across two runs: 1.1–1.9 ms.**

⇒ The between-option spread sits **inside** the within-option noise. The tail is even
less stable: `law_docs` p95 moved 54.5 → 104.3 ms (+91%) between runs, and
`idx_default` moved 109.0 → 65.2 ms (−40%).

### 7.4 Findings

**Finding 10 — Index choice does not change retrieval results at this scale.**
All four indexes produce identical hit rate, top-1 and MRR. This independently confirms
the decision recorded in `DESIGN.md` §6 (keep the server default): its switch condition
was *"when latency becomes the bottleneck or memory gets tight"*, and at 22,900 chunks
swapping the index does not even move latency.

**Finding 11 — A latency difference must beat run-to-run variance to count.**
Run 1 alone showed a clean-looking ranking ("IVF_FLAT fastest, default slowest").
A repeat reversed it. ⇒ **±1–2 ms is the resolution limit of this setup**, and every
between-index difference measured here falls within it.

### 7.5 The reusable rule (the most valuable output of this experiment)

> **To claim a performance difference, compare the spread *between* options against the
> spread *within* one option across repeated runs. Only if the former is larger is the
> difference real.**
>
> Without the repeat, run 1 would have produced a confident — and wrong — conclusion.
> Note also what made the repeat cheap: the query vectors were pre-computed, so a second
> run cost no embedding calls.

### 7.6 Build cost (secondary, and not comparable across runs)

| Index | Write time |
|---|:--:|
| default | 314.1 s ← **first write after server start (cold)** |
| HNSW M=16 | 265.2 s |
| HNSW M=32 | 262.7 s |
| IVF_FLAT | 264.7 s |

⚠️ Two caveats, stated rather than papered over:
1. The timing is **insert + index build combined**; insert dominates (~255 s), so the
   index-build portion is small. It was not measured separately.
2. The default index's 314 s is a **cold-start artifact**, not an index property —
   it was the first write after the server came up.

---

## 8. Chunk size: quality flat, cost trade-off (2026-10-22)

### 8.1 What was compared

Three chunk configurations over **the same source documents** (25 docs / 20 faq /
1 dialogue / 3 tables), so all three index identical content and differ **only** in
how it is cut:

| Config | chunk_size | overlap | Chunks |
|---|:--:|:--:|:--:|
| small | 300 | 60 | 20,796 |
| **baseline** | **600** | **80** | 8,755 |
| large | 800 | 100 | 5,913 |

> ⚠️ **A first attempt was discarded.** It limited each variant by *chunk count*
> (`--subset-per-form 800`). Coarser chunking then packed the same 800 chunks with
> **more source files**, so the variants saw **different corpora** — and the small
> config appeared 41 points worse purely because two files never made it into the index.
> Limiting by **file count** makes the comparison valid.

### 8.2 Retrieval quality: identical

| Config | Hit rate | Top-1 is expected | MRR | Verdicts |
|---|:--:|:--:|:--:|---|
| 300/60 | 70.6% | 58.8% | 0.8958 | miss 5 / hit 10 / partial 2 |
| 600/80 | 70.6% | 58.8% | 0.8958 | miss 5 / hit 10 / partial 2 |
| 800/100 | 70.6% | 58.8% | 0.8958 | miss 5 / hit 10 / partial 2 |

**Identical to the last digit**, down to *which* five questions miss. ⇒ Within the
300–800 character range, **chunk size does not affect recall on this corpus.**

> The absolute 70.6% is lower than this report's usual 100% because the subset omits
> most of the corpus, so some expected sources are simply absent. All three configs miss
> the **same** questions, so the comparison remains fair.

### 8.3 Costs: they move in opposite directions

| Config | Build (one-off) | Search p50 (per call) | Material tokens (per call) |
|---|:--:|:--:|:--:|
| **300/60** | **728 s (2.1×)** | **23.3 ms (+17%)** | **1,651 (−48%)** |
| 600/80 | 344 s | 19.9 ms | 3,200 |
| **800/100** | **272 s (0.79×)** | **19.4 ms** | 4,052 (+27%) |

**⇒ Finer chunking is *worse* on both build time and search latency** — a 2.4× vector
count, and search cost tracks the number of vectors, not their text length. The only
gain is in the **material handed to the generator**.

### 8.4 The model that makes the decision: one-off vs per-call

Chunk size trades a **one-off capital cost** against a **per-call operating cost**:

```
total(n) = build_cost + n × (search_cost + generation_cost)
```

⇒ **"Which chunk size is better" has no absolute answer — it depends on call volume.**
Because quality is flat (§8.2), the decision can be made **purely on cost.**

| Config | Build | Material per call | Wins when |
|---|:--:|:--:|---|
| 800/100 | lowest | highest | **few calls** (batch jobs, offline analysis) |
| 300/60 | highest | **lowest** | **sustained traffic** (a service answering users) |

**Worked break-even** (using the measured values):
- extra build cost of 300/60 ≈ +0.53 M tokens
- saving per call = 3,200 − 1,651 = **1,549 tokens**
- ⇒ **break-even ≈ 340 calls** (~3 days at 100 q/day; ~34 days at 10 q/day)

### 8.5 Findings

**Finding 12 — Chunk size does not change recall here.** Identical hit rate, top-1 and
MRR when the variants index the same documents.

**Finding 13 — Finer chunking raises build *and* search cost.** It doubles the vector
count; search latency and memory follow that, not the text length. The saving appears
only in prompt material, and accrues per call.

**Finding 14 — The choice is a volume question, not a quality question.** Low volume ⇒
coarse; high volume ⇒ fine. The naive intuition ("smaller chunks are lighter") is wrong
for the retrieval half of the cost.

### 8.6 Limitations

1. **Retrieval only** — generation quality was **not** measured. At 300/60 the average
   chunk is ~138 tokens (≈18 characters of this corpus's fragments), which may hurt
   answer completeness even though recall is unchanged. **This is the main open question.**
2. **Subset, 17 questions** — low resolution; a 1–2 question effect could hide here.
3. **Material tokens measured on a single question** (a real API call, not an estimate),
   so the per-call figure is indicative rather than an average over the set.
4. Absolute numbers will differ on the full 22,900-chunk corpus; the *relationships*
   between configs are what this experiment establishes.

---

## 9. Reproduce

```bash
python evals/run_eval.py --mode single
python evals/run_eval.py --mode multi --per-form 2
python evals/run_eval.py --mode multi --per-form 3
python evals/run_eval.py --mode multi --per-form 5
python evals/run_eval.py --mode hybrid --per-form 3     # dense + BM25 + two-layer RRF
```

Each run writes `results/results_<date>_<collection>_<mode>_pf<N>.jsonl` (per question)
and `results/summary_<date>_<collection>_<mode>_pf<N>.json` (aggregate). Parameters are
recorded inside the summary, so numbers from different configurations are never confused.

**Comparability rule:** the embedding model, collection and `min_score` must stay
identical across runs. Changing the embedding model invalidates all comparisons
(the query-side and index-side models must match).

> ⚠️ **Pool-size rule (learned 2026-10-20):** when two configurations return **different
> numbers of candidates**, do not compare their MRR / top-1 directly — a larger pool both
> raises the hit rate and depresses the rank metrics. Truncate to a common budget `K`
> first (see §6.3).