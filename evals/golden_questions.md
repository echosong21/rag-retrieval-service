# Golden Evaluation Set (v1)

> Retrieval/generation evaluation set for `rag-service`.
> **Every entry's `expected_source` was verified against the corpus on disk** — do not edit
> without re-verifying, or previously recorded numbers become non-comparable.
>
> **Frozen parameters** (must stay identical across runs so numbers are comparable):
> `embedding model` = same as indexing side · `top_k` = 5 · `min_score` = 0.0 · `mode` = single
> (note: switch to `multi` only as an explicitly labelled experiment)

---

## 1. Question set

| id | question | form | expected_source (verified) | difficulty |
|:--:|---|---|---|---|
| D1 | 生产经营单位的主要负责人，在安全生产方面承担什么责任？ | docs | `docs/中华人民共和国安全生产法.md`（第五条） | 易 |
| D2 | 生产经营单位必须建立哪些安全生产制度？ | docs | `docs/中华人民共和国安全生产法.md`（第四条） | 中 |
| D3 | 安全生产工作的方针是什么？ | docs | `docs/中华人民共和国安全生产法.md`（第三条） | 易 |
| D4 | 在中华人民共和国领域内从事生产经营活动的单位，安全生产适用什么法律？ | docs | `docs/中华人民共和国安全生产法.md`（第二条） | 易 |
| F1 | 偷越国（边）境罪判几年？为参加恐怖活动而偷越的怎么判？ | faq | `faq/02_刑法常见问题解答_第01部分.md`（刑法第 322 条，两种量刑） | 易 |
| F2 | 运送他人偷越国（边）境，哪些情形会被加重处罚？ | faq | `faq/02_刑法常见问题解答_第01部分.md`（七年以上；数罪并罚） | 中 |
| F3 | 商标法第六条规定了什么？ | faq | `faq/01_法律条文要点问答卡.md`（商标法第六条） | 易 |
| F4 | 将他人注册商标作为企业名称中的字号使用，会承担什么后果？ | faq | `faq/01_法律条文要点问答卡.md`（商标法第五十八条） | 中 |
| C1 | 我朋友欠了联通的通信费一直不交，会不会被起诉啊？ | dialogues | `dialogues/法律咨询对话实录_第01组.md`（通信服务合同纠纷） | 易 |
| C2 | 订婚后退婚，之前给的彩礼还能要回来吗？ | dialogues | `dialogues/法律咨询对话实录_第01组.md` / `第02组.md`（婚约财产、彩礼返还） | 中 |
| C3 | 公司不给我缴社保，合法吗？ | dialogues | `dialogues/法律咨询对话实录_第*.md`（社会保险类咨询） | 中 |
| T1 | 借款合同纠纷在裁判文书里被归到哪一类案由？ | tables | `tables/01_裁判文书结构化数据.csv`（合同事务 / 借款合同） | 中 |
| T2 | 追索劳动报酬纠纷属于哪一类案件？ | tables | `tables/01_裁判文书结构化数据.csv`（劳动人事 / 工资福利） | 易 |
| T3 | 婚约财产纠纷的裁判文书中，常见关键词有哪些？ | tables | `tables/01_裁判文书结构化数据.csv`（婚约、彩礼、给付、返还） | 难 |
| **X1** | **订婚后退婚，之前给的彩礼还能要回来吗？** | **cross** | **`docs/中华人民共和国民法典.md`（第一千零四十二条）+ `faq/` + `tables/01_裁判文书结构化数据.csv`** | **难** |
| **X2** | **生产经营单位的安全生产责任制是如何规定的？** | **cross** | **`docs/中华人民共和国安全生产法.md`（第四条）+ `faq/03_社区安全与犯罪预防问答_第34部分.md`** | **中** |
| **X3** | **偷越国（边）境罪判几年？** | **cross** | **`faq/02_刑法常见问题解答_第01部分.md` + `docs/`（刑法条文）** | **中** |

**合计 17 题**：`docs` 4 ｜ `faq` 4 ｜ `dialogues` 3 ｜ `tables` 3 ｜ **`cross` 3**

---

## 2. 选题说明（为什么是这 17 题）

| 组 | 设计意图 |
|---|---|
| **D1–D4** | 法条层：锚点是**明确条款号**，可精确判定命中；D1/D2 也出现在跨形态题 X2 里，可交叉验证 |
| **F1–F2** | **数字精度探针**：同一法条含"一年以下"与"一年以上三年以下"两种量刑 ⇒ 检验切分是否破坏数字边界 |
| **F3–F4** | 短问答对：锚点为条款号，**召回难度低**，用来验证"基础链路是否正常"（基线锚） |
| **C1–C3** | **口语化鲁棒性**：问题表述与语料书面语差异极大 ⇒ 检验**语义检索而非关键词匹配** |
| **T1–T3** | 结构化形态：⚠️ **刻意改问"可锚定字段"（案由/关键词），不问"判决结论"** —— 因该形态只有元数据字段、无判决结论，问结论会得到"材料中未提及"（那是语料限制、不是检索失败） |
| **X1–X3** ⭐ | **跨形态探针**：直接复用前期实验结论（单路只命中 1 种形态；多路可命中 4 种）⇒ **最能暴露真问题** |

### 已知的选题取舍（记录用，避免以后误判）

| 候选 | 未采用的原因 |
|---|---|
| "网上被人骂了可以起诉吗"（名誉权） | 该主题在 `dialogues/` 仅出现 **16 次**（对比：彩礼 3207、通信费 595）⇒ 语料太稀疏，命中与否噪声大 |
| 社保题锚定到劳动法条文 | `docs/` 中**不存在**劳动法/劳动合同法 ⇒ 该题只能锚定 `dialogues/`，**不可跨形态** |
| 表格型问"婚约财产纠纷一般怎么判" | 该形态**无判决结论字段** ⇒ 必然"材料中未提及"，会污染命中率统计 |

---

## 3. 命中判定口径（跑分脚本按此实现）

| 判定 | 定义 |
|---|---|
| **hit** | 检索结果 top-k 中，**出现 `expected_source` 里的任一文件**（按 `source` 路径匹配） |
| **partial**（仅 cross 题） | 期望多个来源，**只命中其中一部分** ⇒ 记录 `命中数/期望数` |
| **miss** | top-k 中**无任何期望来源** ⇒ **必须写失败归因** |
| **指标** | `总体命中率` = hit+partial 计入 / 总数；**`分形态命中率`**（⭐ 最关键）；`延迟`（均值/最大）|

---

## 4. Baseline results

Recorded from actual runs (full detail: [`EVAL_REPORT.md`](EVAL_REPORT.md)).

| Configuration | Candidates | Overall | docs | faq | dialogues | tables | cross | Latency (mean) |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| single (`top_k=5`) | 5 | 94.1% | 100% | 100% | 100% | 100% | **66.7%** | 568 ms |
| multi (`per_form=2`) | 8 | 94.1% | 100% | 100% | **66.7%** | 100% | **100%** | 351 ms |
| **multi (`per_form=3`)** | **12** | **100%** | 100% | 100% | 100% | 100% | 100% | 392 ms |
| multi (`per_form=5`) | 20 | 100% | 100% | 100% | 100% | 100% | 100% | 455 ms |

**Operating point: `per_form=3`** — beyond it accuracy is flat while latency keeps rising.

### Failure attribution

| Configuration | id | Verdict | Attribution |
|---|:--:|:--:|---|
| single | X1 | 0/3 miss | Single route spent all slots on one data form; cross-form recall is unreachable without per-form routing |
| `per_form=2` | C3 | 0/1 miss | Candidate budget too small — the largest corpus lost its slots; resolved at `per_form=3` |

---

## 5. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-16 | 首版建立（17 题）；所有 `expected_source` 已对语料实测核验 |