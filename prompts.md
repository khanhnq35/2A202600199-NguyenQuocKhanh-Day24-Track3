# Prompts Log — Lab 24

> Ghi lại các AI prompts đã dùng trong quá trình thực hiện lab (academic integrity).

---

## Phase B — LLM-as-Judge Prompts

### B.1 Pairwise Judge Prompt (`phase-b/judge.py`)

```
Bạn là một chuyên gia đánh giá chất lượng câu trả lời hệ thống RAG.

Câu hỏi: {question}
Ngữ cảnh tham chiếu: {context}

Câu trả lời A:
{answer_a}

Câu trả lời B:
{answer_b}

Tiêu chí đánh giá (theo thứ tự ưu tiên):
1. Độ chính xác theo ngữ cảnh — câu trả lời có bám sát tài liệu không?
2. Độ đầy đủ — có trả lời đủ ý câu hỏi không?
3. Độ súc tích — không thừa, không thiếu
4. Văn phong tự nhiên, dễ đọc

Trả về JSON (chỉ JSON, không giải thích):
{"winner": "A" | "B" | "Tie", "reason": "<giải thích ngắn 1 câu>"}
```

**Model:** `gemini-2.5-pro` (JUDGE_LLM)  
**Technique:** Swap-and-average — chạy 2 lần với A↔B đảo vị trí, chỉ count win nếu nhất quán.

---

### B.2 Absolute Scoring Prompt (`phase-b/judge.py`)

```
Bạn là chuyên gia đánh giá hệ thống RAG tiếng Việt.

Câu hỏi: {question}
Ngữ cảnh: {context}
Câu trả lời: {answer}
Đáp án chuẩn: {ground_truth}

Chấm điểm 4 tiêu chí, mỗi tiêu chí 1-5:
- accuracy: độ chính xác so với đáp án chuẩn và ngữ cảnh
- relevance: độ liên quan đến câu hỏi
- conciseness: ngắn gọn súc tích (5=rất ngắn gọn, 1=quá dài/vòng vo)
- helpfulness: mức độ hữu ích thực tế cho người dùng

Trả về JSON (chỉ JSON):
{"accuracy": <1-5>, "relevance": <1-5>, "conciseness": <1-5>, "helpfulness": <1-5>, "reasoning": "<1 câu>"}
```

**Model:** `gemini-2.5-pro`

---

## Phase C — Guardrails Prompts

### C.2 Topic Scope Validator (`phase-c/input_guard.py`)

```
Phân loại câu hỏi sau có thuộc các chủ đề được phép hay không.
Chủ đề được phép: bảo vệ dữ liệu cá nhân, nghị định 13, thuế GTGT, 
                  tờ khai thuế, pháp luật Việt Nam, tài chính doanh nghiệp
Câu hỏi: "{query}"

Trả về JSON: {"is_on_topic": true/false, "reason": "<ngắn gọn 1 câu>"}
```

**System:** `Bạn là chuyên gia phân loại chủ đề tiếng Việt.`  
**Model:** `gemini-2.5-pro` (DEFAULT_LLM)

---

## Phase A — RAGAS Evaluation

RAGAS sử dụng internal prompts cho 4 metrics. Các wrapper custom:

- `VertexChatModel._generate()` → gọi `call_llm()` với Gemini 2.5 Pro
- `VertexEmbeddings.embed_documents()` → gọi `get_embeddings()` với text-embedding-004
- `RunConfig(max_workers=2, timeout=120)` → giảm timeout errors

---

## AI Tools sử dụng trong Lab

| Tool | Mục đích |
|---|---|
| Claude Sonnet 4.6 (Claude Code) | Implement các phase, debug, review code |
| Gemini 2.5 Pro (Vertex AI) | RAG generation + LLM judge + RAGAS evaluation |
| Gemini 2.5 Flash (Vertex AI) | Topic guard classifier |
| Llama Guard 3 (Groq) | Output safety check |
| text-embedding-004 (Vertex AI) | Document + query embeddings |
