# Failure Cluster Analysis

## Bottom 10 Questions

| # | Question (truncated) | Type | F | AR | CP | CR | Avg | Cluster |
|---|---|---|---:|---:|---:|---:|---:|---|
| 1 | quyen tu bao ve cua chu the du lieu voi su dong y trong diu 11 co lien wan gi vo | multi_context | 0.838 | 0.743 | 0.762 | 0.775 | 0.779 | C1 |
| 2 | tôi không hiểu lắm, cái Nghị định này nó có hiệu lực từ bao giờ mà sao giờ mới n | multi_context | 0.841 | 0.812 | 0.769 | 0.782 | 0.801 | C1 |
| 3 | Sự đồng ý của chủ thể dữ liệu là sao và họ phải làm gì để đồng ý, ví dụ như im l | multi_context | 0.848 | 0.826 | 0.761 | 0.777 | 0.803 | C1 |
| 4 | Dựa trên các quy định được cung cấp, khi nào một tổ chức được coi là thực hiện h | multi_context | 0.829 | 0.875 | 0.749 | 0.763 | 0.804 | C1 |
| 5 | Theo các quy định về bảo vệ dữ liệu cá nhân, sau khi một tổ chức đã thực hiện ng | multi_context | 0.836 | 0.892 | 0.752 | 0.767 | 0.812 | C1 |
| 6 | Nếu chủ thể dữ liệu muốn xem dữ liệu cá nhân của mình và sau đó chỉnh sửa thì họ | multi_context | 0.862 | 0.814 | 0.780 | 0.794 | 0.812 | C1 |
| 7 | xử lý dữ liệu cá nhân nhạy cảm có cần phải thông báo không và sự đồng ý phải như | reasoning | 0.854 | 0.847 | 0.767 | 0.783 | 0.813 | C2 |
| 8 | Tôi là DPO và đang xem xét nghi đinh 13/2023. Tôi thấy nghị định có dựa trên **B | multi_context | 0.840 | 0.883 | 0.762 | 0.776 | 0.815 | C1 |
| 9 | Theo quy định của pháp luật, một "chủ thể dữ liệu" có những quyền hạn và nghĩa v | multi_context | 0.853 | 0.828 | 0.785 | 0.797 | 0.816 | C1 |
| 10 | Tôi đang xem nghị định, cái định nghĩa 'Bên thứ ba' ở trang 4 nó là ai thì tôi b | multi_context | 0.861 | 0.830 | 0.784 | 0.797 | 0.818 | C1 |

## Clusters Identified

### Cluster C1: Multi-context retrieval gaps
**Pattern:** Questions combine VAT declaration facts with legal clauses or require more than one parent chunk.
**Examples:**
- quyen tu bao ve cua chu the du lieu voi su dong y trong diu 11 co lien wan gi voi nhau khong?
- tôi không hiểu lắm, cái Nghị định này nó có hiệu lực từ bao giờ mà sao giờ mới nghe nói, mà công ty tôi là công ty nhỏ mới lập thì có được miễn không, rồi nếu mà muốn xin dữ liệu cá nhân của người ta thì có gửi qua mạng được không hay phải lên tận nơi theo cái Mẫu 01, 02 trong phụ lục của cái Nghị định đó?
**Root cause:** `RERANK_TOP_K=10` can still surface only one side of a multi-hop question when BM25 and dense retrieval agree on the same local chunk.
**Proposed fix:** Increase `HYBRID_TOP_K` from 50 to 80 for multi-context queries and keep at least 2 distinct `parent_id` values after reranking.

### Cluster C2: Context recall weaknesses
**Pattern:** The answer needs enumerated legal conditions, but retrieved context may miss one clause.
**Examples:**
- xử lý dữ liệu cá nhân nhạy cảm có cần phải thông báo không và sự đồng ý phải như thế nào
- cho tôi hỏi, cái hoạt động mà chuyển dữ liệu cá nhân của công dân Việt Nam tới một địa điểm ở ngoài lãnh thổ của nước Cộng hòa xã hội chủ nghĩa Việt Nam thì cái định nghĩa nó nói là sao vậy?
**Root cause:** Long legal lists are split across child chunks, so recall can drop when only the top parent is used.
**Proposed fix:** Add neighboring parent expansion and tune `HIERARCHICAL_PARENT_SIZE` from 2048 to 3072 for decree sections with enumerations.

### Cluster C3: Noisy or informal user phrasing
**Pattern:** Colloquial questions reduce lexical overlap and can lower answer relevancy.
**Examples:**
- Nghị định 13/2023/NĐ-CP về bảo vệ dữ liệu cá nhân có căn cứ vào Bộ luật Dân sự nào?
- Tôi đang xem xét lại các thông tin của công ty và có thắc mắc là liệu dữ liẹu cá nhan mà phan ánh hoạt động hay lịch sử hoạt động trên không gian mạng thì có được xếp vào loại dữ liệu cá nhân theo quy định hay không?
**Root cause:** Search query is passed directly into BM25/dense retrieval without query normalization.
**Proposed fix:** Add a query rewrite step before `HybridSearch.search()` and keep the original query for final answer generation.
