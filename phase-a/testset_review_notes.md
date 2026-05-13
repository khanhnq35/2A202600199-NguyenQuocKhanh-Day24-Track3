# Manual Review: Synthetic Test Set (Phase A)

**Date:** 2026-05-13  
**Total Questions Reviewed:** 10  
**Scope:** Rows sampled from `phase-a/testset_v1.csv` after merging Day 18 questions with generated RAGAS questions.

| Row | Question | Evolution | Review Notes | Action Taken |
|---:|---|---|---|---|
| 0 | Tên người nộp thuế và mã số thuế trong tờ khai thuế GTGT Mẫu số 01/GTGT là gì? | simple | Clear single-fact lookup from the VAT declaration. Ground truth contains the exact taxpayer and tax code. | Kept. |
| 1 | Thuế giá trị gia tăng phải nộp của hoạt động sản xuất kinh doanh trong kỳ 4 năm 2024 là bao nhiêu? | simple | Good numeric lookup, but wording "kỳ 4 năm 2024" was ambiguous compared with source wording. | Normalized in review to "Quý 4 năm 2024" in downstream usage. |
| 2 | Nghị định 13/2023/NĐ-CP áp dụng đối với những đối tượng nào? | simple | Good legal recall question; answer enumerates all applicable subject groups. | Kept. |
| 20 | Là kế toán viên đang rà soát tờ khai thuế GTGT mẫu 01/GTGT... | simple | Longer than typical simple query but still answerable from one VAT declaration context. | Kept; useful for testing verbose user style. |
| 21 | tổng doanh thu và thuế giá trị gia tăng là nhiêu? | simple | Informal Vietnamese and missing capitalization, but realistic user query. | Kept to test robustness to noisy phrasing. |
| 22 | cái bà TRỊNH THỊ SANG là ai mà ký vô đây | simple | Colloquial phrasing; answer is grounded in signature section. | Kept to test informal language handling. |
| 33 | làm phiếu yêu cầu dữ liệu cá nhân thì ngoài số thẻ căn cước công dân, cần điền thêm mấy cái thông tin gì nữa vậy? | reasoning | Requires collecting several required fields from the request form. Good reasoning sample. | Kept. |
| 34 | Chủ thể dữ liệu có quyền yêu cầu xóa dữ liệu cá nhân của mình trong những trường hợp nào? | reasoning | High-quality legal enumeration question; ground truth maps to multiple clauses. | Kept. |
| 35 | Bộ luật Dân sự liên quan nghị định 13 thế nào, và người đại diện theo bộ luật đó muốn yêu cầu dữ liệu cá nhân làm sao? | reasoning | Multi-step relation between legal basis and representative request process. | Kept. |
| 36 | Theo Nghị định 13, định nghĩa Chủ thể dữ liệu là gì và sự đồng ý của Chủ thể dữ liệu cho việc xử lý dữ liệu cá nhân được quy định như thế nào? | reasoning | Combines two definitions and related processing rules; suitable as reasoning/multi-context stress case. | Kept. |

## Changes Made During Review

- Added/standardized the required `contexts` column in `testset_v1.csv`; legacy Day 18 rows use ground-truth-backed context text where the generator did not provide `reference_contexts`.
- Normalized `evolution_type` labels to the lab categories: `simple`, `reasoning`, and `multi_context`.
- Adjusted the distribution to 25 simple, 13 reasoning, and 12 multi-context questions, matching the requested 50% / 25% / 25% split within a 50-question integer test set.

## Observations

- The generated questions are mostly grounded in two domains: Nghị định 13/2023/NĐ-CP and VAT declaration data.
- Several generated questions intentionally use colloquial Vietnamese; this is useful for realistic RAG evaluation but may slightly reduce answer-relevancy scores.
- Multi-context questions are longer and should be watched in failure analysis because retrieval can miss one of the required clauses.
