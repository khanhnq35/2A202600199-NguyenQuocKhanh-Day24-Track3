# Day 24 — Kế hoạch thực hiện Lab: Full Evaluation & Guardrail System

> **Tổng thời gian:** ~4-6 giờ | **Pass:** ≥ 60/100 | **Excellent:** ≥ 90/100
> **Deliverables:** GitHub repo + Blueprint document + Demo video 5 phút

---

## Tài sản tái sử dụng từ Day 18

> [!IMPORTANT]
> Pipeline Day18 (`Day18-Track3-Production-RAG-D6-C401/`) đã implement đầy đủ và scores RAGAS **rất cao**.
> Copy project Day18 làm nền tảng, không build RAG từ đầu.

| Tài sản Day18 | Dùng cho | Cần chỉnh gì |
|---|---|---|
| `src/pipeline.py` → `run_query(q, search, reranker, parent_lookup)` | Phase A (A.2) | Trả về `(answer, contexts)` — đúng format RAGAS |
| `src/m4_eval.py` → `evaluate_ragas()`, `failure_analysis()` | Phase A (A.2, A.3) | Thêm export CSV/JSON theo format Lab 24 |
| `src/utils.py` → `call_llm()`, `get_embeddings()` | Phase A, B, C | Hỗ trợ sẵn Vertex AI + OpenAI — dùng cho Judge & Guards |
| `test_set.json` (20 Qs) | Phase A (A.1) | Có sẵn 20 Qs, cần gen thêm 30 Qs |
| `data/` (Nghị định 13 + BCTC, ~93KB text) | Phase A (A.1) | Đủ cho TestsetGenerator |
| `config.py` + `.env` (GCP Vertex AI) | All | LLM = Gemini 2.5, Embedding = text-embedding-004 |
| RAGAS scores cũ: F=0.95, AR=0.86, CP=0.95, CR=0.90 | Phase A (A.2) | Dùng làm "Version A" cho Pairwise Judge ở Phase B |

**Cần xây hoàn toàn mới:** Phase B (Judge + Kappa) · Phase C (Guardrails) · Phase D (Blueprint)

---

## Phase 0 — Setup & Prerequisites (15 phút)

### Bước 0.1 — Copy Day18 + tạo repo mới
```bash
cp -r Day18-Track3-Production-RAG-D6-C401 lab24-eval-guardrails-khanh
cd lab24-eval-guardrails-khanh
rm -rf .git && git init
```

### Bước 0.2 — Cài thêm dependencies cho Lab 24
```bash
# Tái sử dụng .venv Day18, chỉ cài thêm packages mới
source .venv/bin/activate
pip install presidio-analyzer presidio-anonymizer  # Phase C: PII
pip install scikit-learn matplotlib               # Phase B: Kappa + charts
pip install requests                               # Phase C: Groq API
pip freeze > requirements.txt
```

### Bước 0.3 — Tạo cấu trúc thư mục Lab 24
```bash
mkdir -p phase-a phase-b phase-c phase-d .github/workflows demo scripts
touch README.md prompts.md
```

### Bước 0.4 — Verify pipeline Day18 còn chạy
```bash
# Quick smoke test
python -c "
from src.pipeline import build_pipeline, run_query
search, reranker, parent_lookup = build_pipeline()
answer, contexts = run_query('Nghị định 13 là gì?', search, reranker, parent_lookup)
print(f'Answer: {answer[:100]}...')
print(f'Contexts: {len(contexts)} chunks retrieved')
"
```

### Bước 0.5 — Verify API keys
- [ ] GCP Vertex AI (`GCP_PROJECT_ID` trong `.env`) — cho RAG + Eval + Judge
- [ ] Groq API key (`GROQ_API_KEY`) — cho Llama Guard 3 (đăng ký groq.com nếu chưa có)
- [ ] HuggingFace token — nếu chạy Llama Guard self-hosted

> [!CAUTION]
> **Không bắt đầu code nếu pipeline Day18 chưa chạy.** Test `run_query()` trước.

### ✅ Validate Phase 0
- [ ] `python -c "from src.pipeline import build_pipeline; print('OK')"` — import thành công
- [ ] `run_query()` trả về `(answer, contexts)` hợp lệ
- [ ] Cấu trúc thư mục `phase-a/`, `phase-b/`, `phase-c/`, `phase-d/` đã tạo
- [ ] `.env` có `GCP_PROJECT_ID`, `GROQ_API_KEY`

---

## Phase A — RAGAS Evaluation (60 phút, 30 điểm)

### Bước A.1 — Synthetic Test Set Generation (15') — 8đ

**Context:** Day18 đã có 20 Qs trong `test_set.json`, cần bổ sung thêm 30 Qs.

**Việc cần làm:**
1. Dùng `TestsetGenerator` với corpus `data/*.md` → generate 30 questions mới
2. Merge 20 Qs cũ + 30 Qs mới → đảm bảo distribution 50/25/25
3. Thêm column `evolution_type` cho 20 Qs cũ (đánh thủ công: phần lớn là `simple`)
4. Save → `phase-a/testset_v1.csv`
5. Manual review ≥ 10 câu mới, ghi vào `phase-a/testset_review_notes.md`
6. Chỉnh sửa ≥ 1 câu (chứng minh review thực sự)

**Lưu ý:**
- LLM cho generator: dùng Gemini qua `call_llm()` hoặc `gpt-4o-mini` nếu có OpenAI key
- Corpus domain: **Pháp lý VN** (Nghị định bảo vệ DLCN + Tờ khai thuế GTGT)
- 20 Qs cũ đã được verify chất lượng tốt → giữ nguyên
- Nếu `TestsetGenerator` gặp lỗi với Vertex AI wrapper → adapt `VertexRagasLLM` từ `m4_eval.py`

**✅ Validate A.1:**
- [ ] `testset_v1.csv` ≥ 50 rows
- [ ] Có đủ 4 cột: `question`, `ground_truth`, `contexts`, `evolution_type`
- [ ] `df['evolution_type'].value_counts()` đúng tỷ lệ 50/25/25
- [ ] `testset_review_notes.md` có ≥ 10 câu review
- [ ] ≥ 1 câu đã được chỉnh sửa

---

### Bước A.2 — Run RAGAS 4 Metrics (20') — 10đ

**Context:** Day18 đã có `evaluate_ragas()` + `VertexRagasLLM` wrapper. Tái sử dụng trực tiếp.

**Việc cần làm:**
1. Build pipeline: `search, reranker, parent_lookup = build_pipeline()`
2. Chạy `run_query()` trên mỗi question trong testset → lấy `(answer, contexts)`
3. Gọi `evaluate_ragas()` từ `m4_eval.py` — đã có sẵn 4 metrics
4. **Thêm export** → `phase-a/ragas_results.csv` + `phase-a/ragas_summary.json` (Day18 chỉ export JSON)
5. Log total API cost vào README

**Day18 scores (benchmark so sánh):**

| Metric | Day18 (20Qs) | Lab24 Target | Min OK |
|---|---|---|---|
| Faithfulness | **0.95** | ≥ 0.85 | 0.75 |
| Answer Relevancy | **0.864** | ≥ 0.80 | 0.70 |
| Context Precision | **0.95** | ≥ 0.70 | 0.60 |
| Context Recall | **0.90** | ≥ 0.75 | 0.65 |

**Lưu ý:**
- Pipeline Day18 dùng `ThreadPoolExecutor(max_workers=20)` → nhanh nhưng tốn API
- Judge LLM = `gemini-2.5-pro` (config trong `.env`), **lock version này xuyên suốt**
- Scores Day18 rất cao → kỳ vọng 50 Qs mới sẽ có scores tương đương hoặc thấp hơn chút

**✅ Validate A.2:**
- [ ] `ragas_results.csv` có 4 metric columns cho 50 rows
- [ ] `ragas_summary.json` có 4 aggregate scores (F, AR, CP, CR)
- [ ] Total cost ghi rõ vào README

---

### Bước A.3 — Failure Cluster Analysis (15') — 8đ

**Context:** Day18 đã có `failure_analysis()` trong `m4_eval.py`, nhưng format khác Lab 24 yêu cầu.

**Việc cần làm:**
1. Dùng kết quả từ A.2 → gọi `failure_analysis(per_question, bottom_n=10)`
2. **Refactor output** thành markdown format Lab 24 (bảng + clusters)
3. Day18 đã identify 2 clusters: "Missing relevant chunks" + "LLM hallucinating" → mở rộng thêm
4. Proposed fix phải **cụ thể** cho kiến trúc Day18 (VD: tăng `RERANK_TOP_K`, tune `HYBRID_TOP_K`)
5. Save → `phase-a/failure_analysis.md`

**Clusters có thể gặp (dựa trên Day18 report):**
- **C1: Missing relevant chunks** (context_recall thấp) → fix: tăng `BM25_TOP_K`/`DENSE_TOP_K`
- **C2: LLM hallucinating** (faithfulness thấp) → fix: tighten prompt, lower temperature
- **C3: Answer doesn't match question** (AR thấp) → fix: improve system prompt trong `pipeline.py`

**✅ Validate A.3:**
- [ ] Bảng bottom 10 questions đầy đủ scores
- [ ] ≥ 2 clusters distinct
- [ ] Mỗi cluster ≥ 2 examples + proposed fix cụ thể (tham chiếu config Day18)

---

### Bước A.4 — CI/CD Integration Plan (10') — 4đ

**Việc cần làm:**
1. Viết `.github/workflows/eval-gate.yml`
2. Viết `scripts/run_eval.py` — import `evaluate_ragas()` từ Day18, thêm threshold gate

**Lưu ý:**
- Không cần push lên GitHub thật
- Script `run_eval.py` nên import trực tiếp từ `src.m4_eval`

**✅ Validate A.4:**
- [ ] `.yml` file valid YAML
- [ ] Có threshold gate (exit code 1 nếu metric < target)
- [ ] Có artifact upload
- [ ] `scripts/run_eval.py` tồn tại và import được

---

## Phase B — LLM-as-Judge & Calibration (60 phút, 25 điểm)

### Bước B.1 — Pairwise Judge Pipeline (20') — 10đ

**Context:** Dùng `call_llm()` từ Day18 utils làm LLM judge. So sánh 2 versions:
- **Version A:** RAG hiện tại (Day18 pipeline)
- **Version B:** Variant đơn giản (VD: bỏ reranker, hoặc dùng `naive_baseline.py`)

**Việc cần làm:**
1. Tạo file `phase-b/judge.py`
2. Implement `pairwise_judge_with_swap()` dùng `call_llm()` từ `src/utils.py`
3. Lấy 30 Qs → chạy cả 2 pipelines → thu được `answer_a`, `answer_b` cho mỗi Q
4. Swap-and-average: chạy judge 2 lần, flip winner ở run 2
5. Save → `phase-b/pairwise_results.csv`

**Lưu ý:**
- `call_llm()` hỗ trợ Gemini → dùng `JUDGE_LLM` (gemini-2.5-pro) cho consistency
- Day18 có sẵn `naive_baseline.py` → dùng làm Version B (pipeline đơn giản hơn)
- **Swap-and-average BẮT BUỘC** — position bias mitigation

**✅ Validate B.1:**
- [ ] Function có swap-and-average
- [ ] JSON parse robust (có fallback khi parse error)
- [ ] ≥ 30 questions evaluated
- [ ] `pairwise_results.csv` có columns: `question`, `answer_a`, `answer_b`, `winner_after_swap`, `run1_winner`, `run2_winner`

---

### Bước B.2 — Absolute Scoring với Rubric (10') — 5đ

**Việc cần làm:**
1. Implement `absolute_score()` trong `phase-b/judge.py` — dùng `call_llm()`
2. 4 dimensions: accuracy, relevance, conciseness, helpfulness (1-5)
3. `overall` = average of 4
4. Chạy trên 30 questions (answers từ pipeline chính)
5. Save → `phase-b/absolute_scores.csv`

**✅ Validate B.2:**
- [ ] 4 dimensions scored independently
- [ ] Overall = average of 4
- [ ] `absolute_scores.csv` có 30 rows

---

### Bước B.3 — Human Calibration với Cohen's Kappa (20') — 8đ

**Việc cần làm:**
1. Sample 10 cặp từ `pairwise_results.csv`
2. **Tự đọc và judge thủ công** 10 cặp → save `phase-b/human_labels.csv`
3. Compute Cohen's kappa vs LLM judge
4. Interpret theo bảng kappa scale
5. Nếu kappa < 0.6 → viết root cause analysis

**Bảng interpret kappa:**

| Kappa | Ý nghĩa | Hành động |
|---|---|---|
| < 0.2 | Slight — không tin được | Re-check prompt + re-label |
| 0.2–0.4 | Fair — yếu | Identify bias trong B.4 |
| 0.4–0.6 | Moderate | Label thêm 20 cặp |
| ≥ 0.6 | Substantial — production-ready ✓ | Move on |

**Lưu ý:**
- Normalize labels trước khi compute ("A"/"B"/"tie")
- Corpus là tiếng Việt → đọc kỹ answer content, đừng judge bằng length

**✅ Validate B.3:**
- [ ] `human_labels.csv` có 10 labels với `confidence` + `notes`
- [ ] Cohen's kappa computed + interpretation đúng
- [ ] Root cause analysis nếu kappa < 0.6

---

### Bước B.4 — Bias Observations Report (10') — 2đ

**Việc cần làm:**
1. Quantify **Position bias**: % A wins khi listed first (expected ~50%, >55% = bias)
2. Quantify **Length bias**: correlation answer length vs judge preference
3. Tạo ≥ 1 chart (matplotlib)
4. Viết mitigation strategy
5. Save → `phase-b/judge_bias_report.md`

**✅ Validate B.4:**
- [ ] ≥ 2 biases quantified với numbers
- [ ] ≥ 1 chart hoặc table
- [ ] Mitigation strategy documented

---

## Phase C — Guardrails Stack (90 phút, 35 điểm)

> [!IMPORTANT]
> **Domain context cho Guardrails:** Corpus Day18 là tài liệu pháp lý VN (Nghị định bảo vệ DLCN + Tờ khai thuế GTGT).
> - `allowed_topics` cho Topic Guard: `["bảo vệ dữ liệu cá nhân", "nghị định 13", "thuế GTGT", "tờ khai thuế", "pháp luật Việt Nam"]`
> - PII test cases nên có: CCCD, mã số thuế, số điện thoại VN — phù hợp domain

### Bước C.1 — Input Guardrail: PII Redaction (20') — 8đ

**Việc cần làm:**
1. Tạo `phase-c/input_guard.py` — class `InputGuard`:
   - Layer 1: VN regex (CCCD 12 số, phone `(+84|0)\d{9,10}`, tax code, email)
   - Layer 2: Presidio NER (multilingual)
2. Build 10 test inputs phù hợp domain pháp lý VN:
   - VD: "Số CCCD của tôi là 012345678901, mã số thuế 0106769437"
   - VD: "Liên hệ Trịnh Thị Sang, SĐT 0987654321"
3. Track latency per request
4. Save → `phase-c/pii_test_results.csv`

**Lưu ý:**
- Edge cases: empty, very long (5000 chars), multilingual
- Presidio EN sẽ miss tên VN (Nguyễn Văn A) → expected, ghi vào notes

**✅ Validate C.1:**
- [ ] Detection rate ≥ 80%
- [ ] Latency P95 < 50ms
- [ ] Edge cases handled
- [ ] `pii_test_results.csv` columns: `input`, `output`, `pii_found`, `latency_ms`

---

### Bước C.2 — Input Guardrail: Topic Scope Validator (15') — 6đ

**Việc cần làm:**
1. **Khuyến nghị Option 2 (LLM zero-shot)** — dùng `call_llm()` sẵn có
2. `allowed_topics = ["bảo vệ dữ liệu cá nhân", "nghị định 13", "thuế GTGT", "tờ khai thuế", "pháp luật Việt Nam"]`
3. Test 20 inputs (10 on-topic pháp lý, 10 off-topic: cooking, sports, weather...)
4. Graceful fallback: "Xin lỗi, câu hỏi này nằm ngoài phạm vi tài liệu pháp lý. Vui lòng hỏi về..."

**✅ Validate C.2:**
- [ ] Accuracy ≥ 75% (excellent: ≥ 95%)
- [ ] Refuse rate documented
- [ ] Graceful fallback message khi off-topic (tiếng Việt)

---

### Bước C.3 — Adversarial Testing (15') — 6đ

**Việc cần làm:**
1. Build 20 adversarial inputs (DAN ×5, Roleplay ×5, Split ×3, Encoding ×3, Injection ×4)
2. Chạy qua full input guard chain (PII + Topic)
3. Test 10 legitimate queries (từ `test_set.json` Day18) → đo false positive rate
4. Save → `phase-c/adversarial_test_results.csv`

**✅ Validate C.3:**
- [ ] 20 adversarial inputs tested
- [ ] Detection rate ≥ 70% (excellent: ≥ 95%)
- [ ] False positive rate ≤ 10%

---

### Bước C.4 — Output Guardrail: Llama Guard 3 (20') — 8đ

**Việc cần làm:**
1. Dùng **Groq API** (Option B, free tier) — không cần GPU
2. Tạo `phase-c/output_guard.py` — class `OutputGuardAPI`
3. Craft 10 unsafe outputs + 10 safe outputs
4. Test + measure latency

**Lưu ý:**
- Đăng ký groq.com, lấy API key, model = `llama-guard-3-8b`
- Thêm `GROQ_API_KEY` vào `.env`

**✅ Validate C.4:**
- [ ] Llama Guard return `safe/unsafe`
- [ ] Detection ≥ 80% trên 10 unsafe
- [ ] False positive ≤ 20% trên 10 safe
- [ ] Latency P95 measured

---

### Bước C.5 — Full Stack Integration & Latency Benchmark (20') — 7đ

**Việc cần làm:**
1. Tạo `phase-c/full_pipeline.py` — integrate:
   - **L1 (parallel):** `InputGuard.sanitize()` + `TopicGuard.check()`
   - **L2:** `run_query()` từ Day18 pipeline
   - **L3:** `OutputGuardAPI.check()`
   - **L4 (async):** Audit log (fire-and-forget)
2. Benchmark ≥ 100 requests
3. Report P50/P95/P99 per layer + total overhead vs baseline (Day18 no-guardrail)
4. Save → `phase-c/latency_benchmark.csv`

**Lưu ý:**
- L2 = Day18 pipeline → đã có sẵn `build_pipeline()` + `run_query()`
- L1 guards chạy **parallel** (asyncio)
- Baseline latency = Day18 `run_query()` đơn thuần

**✅ Validate C.5:**
- [ ] Full stack end-to-end chạy được
- [ ] Benchmark ≥ 100 requests
- [ ] L1 P95 < 50ms, L3 P95 < 100ms
- [ ] P50/P95/P99 report + overhead vs Day18 baseline documented

---

## Phase D — Blueprint Document (30 phút, 10 điểm)

**Việc cần làm:** Viết `phase-d/blueprint.md` (4-6 trang)

### Section 1: SLO Definition (2đ)
- ≥ 5 SLOs với alert thresholds + severity
- Dùng scores Day18 làm baseline: F=0.95, AR=0.86, CP=0.95, CR=0.90

### Section 2: Architecture Diagram (3đ)
- Mermaid diagram show 4 layers
- Label: Presidio, VN Regex, Gemini Judge, Llama Guard 3, Qdrant, BM25+RRF
- Latency annotation per layer

### Section 3: Alert Playbook (3đ)
- ≥ 3 incidents: Faithfulness drop, Latency spike, Guardrail bypass
- Mỗi incident: Severity + Detection + Causes + Investigation + Resolution

### Section 4: Cost Analysis (2đ)
- Monthly cost breakdown (100k queries/month)
- Note: Gemini 2.5 Flash cheaper than GPT-4o-mini → highlight cost advantage

**✅ Validate Phase D:**
- [ ] ≥ 5 SLOs có alert thresholds
- [ ] Architecture diagram clear, 4 layers labeled
- [ ] ≥ 3 incidents trong playbook
- [ ] Cost breakdown có monthly projection

---

## Phase Final — Submission Checklist

### README.md (200-300 từ)
- [ ] Overview 2-3 câu
- [ ] Setup instructions (GCP + Groq keys)
- [ ] Results summary per phase
- [ ] Lessons learned

### Demo Video (5 phút)
- [ ] 1' — RAGAS chạy live trên 5 questions
- [ ] 1' — LLM-Judge so sánh 2 versions (Day18 vs naive_baseline)
- [ ] 2' — Adversarial test: 3 attacks bị block
- [ ] 1' — Latency benchmark P50/P95/P99

### Files bắt buộc
- [ ] `requirements.txt` (pinned versions)
- [ ] `prompts.md` (log AI prompts đã dùng)
- [ ] Tất cả CSV + JSON output files
- [ ] Push to GitHub với commit history rõ ràng

---

## Timeline gợi ý (cập nhật theo Day18 reuse)

| Thời gian | Công việc | Tiết kiệm nhờ Day18 |
|---|---|---|
| 0:00 – 0:15 | Phase 0: Copy Day18 + verify | ⚡ Giảm 15' (có sẵn env + pipeline) |
| 0:15 – 1:00 | Phase A: RAGAS | ⚡ Giảm 15' (có sẵn `evaluate_ragas()` + 20 Qs) |
| 1:00 – 2:00 | Phase B: LLM-Judge | Dùng `call_llm()` + `naive_baseline.py` |
| 2:00 – 3:30 | Phase C: Guardrails | Dùng `run_query()` cho L2, domain context rõ |
| 3:30 – 4:00 | Phase D: Blueprint | Dùng Day18 scores làm baseline SLOs |
| 4:00 – 4:30 | Finalize | README, demo video, push |

**Tổng tiết kiệm:** ~30 phút nhờ tái sử dụng Day18

---

## Lưu ý quan trọng xuyên suốt

> [!WARNING]
> 1. **Commit mỗi 30 phút** — cần git history
> 2. **Log mọi API cost** — Gemini 2.5 Flash rẻ nhưng vẫn track
> 3. **Lock model version** — `JUDGE_LLM=gemini-2.5-pro` xuyên suốt
> 4. **Ghi prompts.md** — academic integrity
> 5. **Stuck > 20 phút → hỏi** — Slack #lab24-eval-guardrails
> 6. **LLM Provider = Vertex AI** — code template Lab 24 dùng OpenAI → cần adapt sang `call_llm()`

## Bonus gợi ý (nếu còn thời gian, max +15đ)

| Bonus | Điểm | Độ khó | Phù hợp vì |
|---|---|---|---|
| Prompt Guard (Meta) | +2 | Easy | Bổ sung injection detection cho C.3 |
| Eval dashboard (Streamlit) | +3 | Medium | Visualize RAGAS scores + latency |
| Cross-judge protocol | +3 | Medium | Dùng cả Gemini + GPT làm judge |
| Blog post | +2 | Easy | Viết về kinh nghiệm dùng Vertex AI cho RAG eval |

> Chọn 1 bonus làm sâu, quality > quantity.
