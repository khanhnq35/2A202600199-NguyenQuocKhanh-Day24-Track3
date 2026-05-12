"""Phase C.5 — Full Stack Integration & Latency Benchmark.

Architecture:
  L1 (parallel): InputGuard.sanitize() + TopicGuard.check()
  L2: run_query() — Day18 RAG pipeline
  L3: OutputGuardAPI.check()
  L4 (async fire-and-forget): audit log
"""

import os
import sys
import time
import json
import csv
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from input_guard import InputGuard, TopicGuard  # noqa
from output_guard import OutputGuardAPI          # noqa
from src.utils import call_llm

# Lazy import RAG pipeline to avoid slow startup during benchmark init
_rag_pipeline = None


def _get_rag_pipeline():
    global _rag_pipeline
    if _rag_pipeline is None:
        from src.pipeline import build_pipeline
        _rag_pipeline = build_pipeline()
    return _rag_pipeline


# ── Audit log (fire-and-forget) ────────────────────────────────────────────────

_audit_log = []
_audit_lock = threading.Lock()


def _audit(event: dict) -> None:
    """Non-blocking append to in-memory audit log."""
    with _audit_lock:
        _audit_log.append(event)


# ── Full pipeline ──────────────────────────────────────────────────────────────

def run_full_pipeline(query: str, use_rag: bool = True) -> dict:
    """
    Execute full guardrail + RAG stack, return timing breakdown.
    Returns:
        {blocked, answer, layer_latencies: {l1, l2, l3}, total_ms}
    """
    t_total = time.perf_counter()
    layer_times: dict = {}

    # ── L1: Input guards (run in parallel threads) ──
    input_guard = InputGuard()
    topic_guard = TopicGuard()

    t_l1 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as ex:
        pii_fut   = ex.submit(input_guard.sanitize, query)
        topic_fut = ex.submit(topic_guard.check, query)
        pii_res   = pii_fut.result()
        topic_res = topic_fut.result()
    layer_times["l1_ms"] = (time.perf_counter() - t_l1) * 1000

    # Block on PII
    if not pii_res["safe"]:
        total_ms = (time.perf_counter() - t_total) * 1000
        threading.Thread(target=_audit, args=({"query": query[:50], "blocked_at": "L1-PII", "total_ms": total_ms},), daemon=True).start()
        return {"blocked": True, "blocked_at": "L1-PII", "answer": pii_res["sanitized_text"],
                "layer_latencies": layer_times, "total_ms": round(total_ms, 2)}

    # Block on topic
    if not topic_res["safe"]:
        total_ms = (time.perf_counter() - t_total) * 1000
        threading.Thread(target=_audit, args=({"query": query[:50], "blocked_at": "L1-Topic", "total_ms": total_ms},), daemon=True).start()
        return {"blocked": True, "blocked_at": "L1-Topic",
                "answer": "Xin lỗi, câu hỏi nằm ngoài phạm vi tài liệu pháp lý. Vui lòng hỏi về Nghị định 13 hoặc thuế GTGT.",
                "layer_latencies": layer_times, "total_ms": round(total_ms, 2)}

    # ── L2: RAG pipeline ──
    t_l2 = time.perf_counter()
    sanitized = pii_res["sanitized_text"]
    if use_rag:
        try:
            search, reranker, parent_lookup = _get_rag_pipeline()
            from src.pipeline import run_query
            answer, _ctx = run_query(sanitized, search, reranker, parent_lookup)
        except Exception as e:
            answer = f"[RAG error: {e}]"
    else:
        # Lightweight stub for pure-latency benchmarking
        answer = call_llm("Trả lời ngắn gọn.", sanitized)
    layer_times["l2_ms"] = (time.perf_counter() - t_l2) * 1000

    # ── L3: Output guard ──
    t_l3 = time.perf_counter()
    out_guard = OutputGuardAPI()
    out_res = out_guard.check(answer)
    layer_times["l3_ms"] = (time.perf_counter() - t_l3) * 1000

    if not out_res["safe"]:
        answer = "[Nội dung vi phạm chính sách đã bị chặn bởi Llama Guard 3]"

    total_ms = (time.perf_counter() - t_total) * 1000
    layer_times["total_ms"] = round(total_ms, 2)

    # L4: fire-and-forget audit
    threading.Thread(
        target=_audit,
        args=({"query": sanitized[:50], "blocked": not out_res["safe"],
               "total_ms": total_ms},),
        daemon=True,
    ).start()

    return {
        "blocked": not out_res["safe"],
        "answer": answer,
        "layer_latencies": layer_times,
        "total_ms": round(total_ms, 2),
    }


# ── Benchmark ──────────────────────────────────────────────────────────────────

BENCHMARK_QUERIES = [
    "Nghị định 13 quy định gì?",
    "Quyền của chủ thể dữ liệu?",
    "Mức thuế GTGT 10% áp dụng khi nào?",
    "Dữ liệu nhạy cảm là gì?",
    "Thời hạn nộp tờ khai thuế?",
    "Điều kiện hoàn thuế GTGT?",
    "Trách nhiệm bên kiểm soát dữ liệu?",
    "Xử phạt vi phạm NĐ 13 thế nào?",
    "Chuyển dữ liệu ra nước ngoài có cần điều kiện gì?",
    "Đăng ký bảo vệ dữ liệu cá nhân ở đâu?",
]


def run_benchmark(n_requests: int = 100, use_rag: bool = False) -> None:
    """Benchmark full stack. use_rag=False for guard-only latency."""
    print(f"=== C.5: Full Stack Benchmark ({n_requests} requests, use_rag={use_rag}) ===")

    # Baseline: guards only, no L2 (measure overhead)
    records = []
    queries_cycle = BENCHMARK_QUERIES * (n_requests // len(BENCHMARK_QUERIES) + 1)
    queries_cycle = queries_cycle[:n_requests]

    for i, q in enumerate(queries_cycle):
        res = run_full_pipeline(q, use_rag=use_rag)
        records.append({
            "index": i,
            "query": q[:60],
            "blocked": res["blocked"],
            "l1_ms": res["layer_latencies"].get("l1_ms", 0),
            "l2_ms": res["layer_latencies"].get("l2_ms", 0),
            "l3_ms": res["layer_latencies"].get("l3_ms", 0),
            "total_ms": res["total_ms"],
        })
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{n_requests} done ...")

    # Stats
    def percentile(data, p):
        return round(float(np.percentile(data, p)), 2) if data else 0

    for layer in ("l1_ms", "l3_ms", "total_ms"):
        vals = [r[layer] for r in records if r[layer] > 0]
        print(f"  {layer}: P50={percentile(vals,50)} P95={percentile(vals,95)} P99={percentile(vals,99)}")

    os.makedirs("phase-c", exist_ok=True)
    with open("phase-c/latency_benchmark.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["index", "query", "blocked", "l1_ms", "l2_ms", "l3_ms", "total_ms"])
        w.writeheader()
        w.writerows(records)

    # Summary JSON
    all_total = [r["total_ms"] for r in records]
    l1_vals = [r["l1_ms"] for r in records]
    l3_vals = [r["l3_ms"] for r in records if r["l3_ms"] > 0]
    summary = {
        "n_requests": n_requests,
        "use_rag": use_rag,
        "l1": {"p50": percentile(l1_vals, 50), "p95": percentile(l1_vals, 95), "p99": percentile(l1_vals, 99)},
        "l3": {"p50": percentile(l3_vals, 50), "p95": percentile(l3_vals, 95), "p99": percentile(l3_vals, 99)},
        "total": {"p50": percentile(all_total, 50), "p95": percentile(all_total, 95), "p99": percentile(all_total, 99)},
    }
    with open("phase-c/latency_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("Saved: phase-c/latency_benchmark.csv + latency_summary.json")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--use-rag", action="store_true",
                        help="Include RAG pipeline in benchmark (slow, costs API)")
    args = parser.parse_args()

    run_benchmark(n_requests=args.n, use_rag=args.use_rag)
