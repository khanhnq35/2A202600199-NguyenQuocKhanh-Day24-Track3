# RAG Evaluation & Guardrail Blueprint

## 1. Hệ thống chỉ số mục tiêu (SLOs)
Dựa trên benchmark Day 18, hệ thống cam kết duy trì các chỉ số sau:

| Metric | Target (SLO) | Threshold (Alert) | Ghi chú |
|---|---|---|---|
| Faithfulness | **≥ 0.90** | < 0.80 | Đảm bảo không ảo giác |
| Answer Relevancy | **≥ 0.85** | < 0.75 | Trả lời đúng trọng tâm |
| Context Precision | **≥ 0.85** | < 0.70 | Độ nhiễu của Retrieval |
| Latency (p95) | **< 8.0s** | > 12.0s | Bao gồm cả Rerank & Guardrails |
| Guardrail Accuracy | **100%** | < 95% | Đặc biệt với PII và Toxic |

## 2. Alert Playbook (Quy trình xử lý)
| Sự cố | Nguyên nhân có thể | Hành động (Action Plan) |
|---|---|---|
| Faithfulness giảm đột ngột | LLM đổi version hoặc Temperature quá cao | 1. Hạ Temp về 0.0. 2. Kiểm tra lại Prompt Template. |
| Context Recall thấp | Tài liệu mới chưa được chunking đúng | 1. Kiểm tra lại logic Hierarchical Chunking. 2. Tăng `top_k` của Retrieval. |
| Guardrail Block nhầm (False Positive) | Topic Guard quá khắt khe | 1. Cập nhật danh sách `allowed_topics`. 2. Fine-tune Prompt phân loại. |

## 3. Phân tích chi phí (Estimation)
Dự toán chi phí cho 1,000 queries (Sử dụng Gemini 2.5 Flash):
- **Retrieval & Rerank**: ~$0.10 (Local embedding/rerank)
- **Generation**: ~$1.20 (Gemini 2.5 Flash)
- **Guardrails**: ~$0.50 (Gemini classification)
- **Evaluation**: ~$5.00 (Nếu chạy RAGAS full mỗi ngày)
- **Tổng cộng**: **~$6.80 / 1,000 queries**.

## 4. Kiến trúc triển khai
Hệ thống được thiết kế theo dạng **Middleware**:
`User Request` -> `Input Guardrails` -> `RAG Pipeline` -> `Output Guardrails` -> `Evaluation (Async)` -> `User`.
