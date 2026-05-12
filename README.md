# Lab 24 — Evaluation & Guardrail System

Dự án triển khai hệ thống đánh giá (Evaluation) và rào chắn (Guardrails) cho RAG Pipeline dựa trên nền tảng Day 18.

## 🚀 Tính năng chính
- **Phase A (RAGAS)**: Đánh giá tự động 4 metrics cốt lõi và phân tích lỗi.
- **Phase B (LLM-as-Judge)**: So sánh Pairwise với kỹ thuật swap-and-average và hiệu chuẩn với con người (Cohen's Kappa).
- **Phase C (Guardrails)**: Hệ thống phòng thủ đa lớp (PII, Topic, Adversarial, Llama Guard 3).
- **Phase D (Blueprint)**: Tài liệu vận hành, SLOs và Playbook.

## 🛠️ Cài đặt
1. Khởi tạo môi trường:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
2. Cấu hình `.env`:
- `GCP_PROJECT_ID`: Project ID của Google Cloud.
- `GROQ_API_KEY`: API Key cho Llama Guard 3.

## 📊 Kết quả (Day 18 Baseline)
- Faithfulness: 0.95
- Answer Relevancy: 0.86
- Context Precision: 0.95
- Context Recall: 0.90
