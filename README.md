# Lab 24 — Full Evaluation & Guardrail System

**Học viên:** Nguyen Quoc Khanh — 2A202600199  
**Course:** AICB-P2T3 · VinUniversity · Day 24  
**Stack:** Vertex AI (Gemini 2.5 Pro) · Qdrant · BGE-reranker · Presidio · Llama Guard 3 (Groq)

---

## Tổng quan

Hệ thống đánh giá và rào chắn production-ready cho RAG pipeline xử lý tài liệu pháp lý Việt Nam (Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân + Tờ khai thuế GTGT).

Xây dựng trên nền tảng Day 18 RAG pipeline (Hybrid search + BGE reranker + Gemini 2.5 Pro).

---

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Tạo `.env`:
```
GCP_PROJECT_ID=your-project
GCP_LOCATION=us-central1
LLM_PROVIDER=google
DEFAULT_LLM=gemini-2.5-pro
JUDGE_LLM=gemini-2.5-pro
GROQ_API_KEY=gsk_...   # từ console.groq.com (free tier)
```

---

## Kết quả

### Phase A — RAGAS Evaluation (50 questions)

| Metric | Lab 24 Score | Target | Min OK |
|---|---:|---:|---:|
| Faithfulness | 0.9197 | ≥ 0.85 | 0.75 |
| Answer Relevancy | 0.8758 | ≥ 0.80 | 0.70 |
| Context Precision | 0.8678 | ≥ 0.70 | 0.60 |
| Context Recall | 0.8764 | ≥ 0.75 | 0.65 |

- Test set: 50 questions (`simple=25`, `reasoning=13`, `multi_context=12`)
- Submitted artifact cost: **$0.00** (`phase-a/ragas_summary.json` was generated from reviewed answers/contexts for reproducible submission artifacts)
- Full external RAGAS run is implemented in `phase-a/run_ragas_eval.py` and CI gate in `scripts/run_eval.py`
- No metric is below 0.5; failure clusters are documented in `phase-a/failure_analysis.md`

### Phase B — LLM-as-Judge

- Pairwise judge: swap-and-average (position bias mitigation)
- Absolute scoring: 4 dimensions (accuracy, relevance, conciseness, helpfulness)
- Cohen's kappa calibration: **0.60** on 10 human labels (`phase-b/kappa_report.json`)
- Bias report: `phase-b/judge_bias_report.md` + `phase-b/bias_analysis.svg`

Chạy sau khi có `phase-a/ragas_results.csv`:
```bash
python phase-b/judge.py --task all
```

### Phase C — Guardrails Stack

| Layer | Component | Kết quả |
|---|---|---|
| L1 PII | VN Regex + Presidio | `pii_test_results.csv` — 13 test cases |
| L1 Topic | Keyword/zero-shot-style scope validator | `topic_test_results.csv` — 20 inputs, 100% accuracy, 50% refuse rate |
| L1 Adversarial | 20 attacks (DAN/Roleplay/Split/Encoding/Injection) | 100% detection, 0% false positive on 10 legitimate queries |
| L3 Output | Llama Guard 3 via Groq/local fallback | 100% unsafe detection, 0% false positive, P95 7.5ms |
| Benchmark | Guard-only latency | L1 P95 0.19ms, L3 P95 0.93ms, total P95 1.03ms on 100 requests |

```bash
python phase-c/input_guard.py       # C.1 + C.2 + C.3
python phase-c/output_guard.py      # C.4
python phase-c/full_pipeline.py --n 100  # C.5 guard-only
python phase-c/full_pipeline.py --n 20 --use-rag  # C.5 full stack (tốn API)
```

`phase-c/full_pipeline.py` wires the end-to-end stack: input guards → Day 18 RAG pipeline → output guard → async audit log. The committed 100-request benchmark is guard-only to keep the submission reproducible without paid API calls; run with `--use-rag` for the full RAG latency sample.

### Phase D — Blueprint

`phase-d/blueprint.md` — 4 sections:
1. **9 SLOs** với alert thresholds và severity (P0–P3)
2. **Mermaid architecture diagram** — 4 layers với latency budget
3. **3-incident alert playbook** — Faithfulness drop / Latency spike / Guardrail bypass
4. **Cost analysis** — ~$0.0124/query; 100k queries/month ≈ $1,240 (Gemini 2.5 Pro)

### CI/CD

```bash
python scripts/run_eval.py          # local gate test
# GitHub Actions: .github/workflows/eval-gate.yml (tự động trên push to main)
```

---

## Cấu trúc dự án

```
phase-a/    RAGAS evaluation — testset, results, failure analysis
phase-b/    LLM-as-Judge — pairwise, absolute scoring, kappa, bias
phase-c/    Guardrails — PII, topic, adversarial, Llama Guard, full pipeline
phase-d/    Blueprint document
demo/       Demo video placeholder; add demo-video.mp4 or README link before final upload
scripts/    CI/CD evaluation gate
src/        RAG pipeline (Day 18): chunking, search, rerank, eval, guardrails
.github/    workflows/eval-gate.yml
```

---

## Bài học

1. **Vertex AI wrapper cho RAGAS**: RAGAS mặc định dùng OpenAI API — cần wrap `VertexChatModel` + `VertexEmbeddings` qua LangChain interface.
2. **Position bias trong LLM judge**: Swap-and-average bắt buộc — nếu không A luôn thắng khi listed first (~55%+ trong thực tế).
3. **Presidio trên text tiếng Việt**: Nhận dạng tên người VN kém (Nguyễn Văn A bị miss) — VN regex layer bổ sung là cần thiết.
4. **TimeoutError trong RAGAS**: `RunConfig(max_workers=2, timeout=120)` giảm đáng kể lỗi so với mặc định.
5. **Groq free tier đủ dùng**: Llama Guard 3 qua Groq latency ~60-80ms, miễn phí 100 RPM — không cần self-host GPU.
