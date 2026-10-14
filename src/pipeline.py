import argparse
import sys,time
from datetime import datetime
from pathlib import Path
import observe

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from langchain_openai import ChatOpenAI,OpenAIEmbeddings
from pymilvus import MilvusClient
from config import settings

COLLECTION = "law_docs"

emb = OpenAIEmbeddings(
    model=settings.EMBED_MODEL,
    base_url=settings.EMBED_BASE_URL,
    api_key=settings.API_KEY,
    check_embedding_ctx_length=False
)
llm = ChatOpenAI(
    model=settings.MODEL,
    base_url=settings.BASE_URL.removesuffix("/chat/completions"),
    api_key=settings.API_KEY
)
client = MilvusClient(uri=settings.MILVUS_URL)

PROMPT_TMPL = """只依据下面材料回答问题；材料中没有的信息就回答"材料中未提及"。

材料：
{contexts}

问题：{question}
"""
logger = observe.setup_logging()
def rag_query(question: str, top_k: int = 3, min_score: float = 0.0) -> dict:
    """min_score=0.0 ⇒ 不过滤，行为与改造前完全一致"""
    stage_ms, contexts, usage, answer, raw = {}, [], None, None, []
    trace_id = observe.new_trace_id()
    status, error = "ok", None
    try:
        t0 = time.perf_counter()
        qvec = emb.embed_query(question)
        stage_ms["embed_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        t0 = time.perf_counter()
        hits = client.search(collection_name=COLLECTION, data=[qvec],
                             limit=top_k,
                             output_fields=["text", "source", "chunk_index"])[0]
        stage_ms["search_ms"] = round((time.perf_counter() - t0) * 1000, 1)

        raw = [{"score": round(h["distance"], 4),
                "source": h["entity"]["source"],
                "text": h["entity"]["text"]} for h in hits]
        contexts = [c for c in raw if c["score"] >= min_score]      # ← 阈值过滤

        t0 = time.perf_counter()
        if contexts:                                                # ← 空上下文保护
            materials = "\n\n".join(f"[{i+1}] 来源：{c['source']}\n{c['text']}"
                                    for i, c in enumerate(contexts))
            resp = llm.invoke(PROMPT_TMPL.format(contexts=materials, question=question))
            answer, usage = resp.content, resp.usage_metadata
        else:
            answer = f"（{len(raw)} 条候选全部低于阈值 {min_score}，无材料可用）"
        stage_ms["generate_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    except Exception as e:
        status, error = "error", repr(e)
        logger.exception("trace=%s 失败：%s", trace_id, e)
        raise
    finally:
        cost = observe.calc_cost(usage)
        span = observe.build_retrieval_span(contexts, raw_n=len(raw))
        observe.write_trace({
            "trace_id": trace_id,
            "ts": datetime.now().isoformat(timespec="seconds"),
            "question": question,
            "params": {"top_k": top_k, "min_score": min_score},     # ← 参数进 trace
            "stage_ms": stage_ms, "usage": usage, "cost_cny": cost,
            "retrieval": span, "status": status, "error": error,
        })
        logger.info("trace=%s status=%s top_k=%s min_score=%s n_raw=%s n_kept=%s stage_ms=%s cost=%.6f元",
                    trace_id, status, top_k, min_score, len(raw), len(contexts), stage_ms, cost)

    return {"answer": answer, "contexts": contexts, "usage": usage, "stage_ms": stage_ms,
            "top_k": top_k, "min_score": min_score, "n_raw": len(raw)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG 查询（可调参实验）")
    parser.add_argument("-q", "--question", default="生产经营单位的安全生产责任制是如何规定的？")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--min-score", type=float, default=0.0)
    args = parser.parse_args()

    out = rag_query(args.question, top_k=args.top_k, min_score=args.min_score)
    print(f"【问题】{args.question}")
    print(f"【参数】top_k={out['top_k']}  min_score={out['min_score']}"
          f"  |  候选 {out['n_raw']} → 保留 {len(out['contexts'])}")
    print(f"【回答】{out['answer']}\n")
    for i, c in enumerate(out["contexts"], 1):
        print(f"  [{i}] score={c['score']} | {c['source']}")
    print(f"【阶段耗时】{out['stage_ms']}")
    print(f"【token】{out['usage']}")