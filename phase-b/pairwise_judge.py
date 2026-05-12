import os
import sys
import pandas as pd
import json
import re

# Add root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import call_llm
from config import JUDGE_LLM

JUDGE_PROMPT = """
Bạn là một chuyên gia đánh giá hệ thống RAG. 
Nhiệm vụ: So sánh hai câu trả lời (A và B) cho cùng một câu hỏi dựa trên ngữ cảnh được cung cấp.

Câu hỏi: {question}
Ngữ cảnh: {context}

Câu trả lời A: {ans_a}
Câu trả lời B: {ans_b}

Tiêu chí đánh giá:
1. Độ chính xác so với ngữ cảnh.
2. Độ đầy đủ và súc tích.
3. Văn phong tự nhiên.

Kết quả trả về chỉ gồm 1 từ duy nhất: "A" nếu A tốt hơn, "B" nếu B tốt hơn, hoặc "Tie" nếu ngang nhau.
"""

def get_judge_decision(q, ctx, ans_a, ans_b):
    prompt = JUDGE_PROMPT.format(question=q, context=ctx, ans_a=ans_a, ans_b=ans_b)
    res = call_llm("Bạn là quan tòa trung lập.", prompt, model_name=JUDGE_LLM)
    
    if "A" in res and "B" not in res: return "A"
    if "B" in res and "A" not in res: return "B"
    return "Tie"

def run_pairwise_comparison(results_a_path="phase-a/ragas_results.csv"):
    print("--- Phase B: Running Pairwise Judge (Swap-and-Average) ---")
    
    # 1. Load results from Version A (Day 18)
    df_a = pd.read_csv(results_a_path)
    
    # 2. Mocking Version B (Naive Baseline) - For demo purposes 
    # In reality, you'd run naive_baseline.py to get these
    df_b = df_a.copy()
    df_b['answer'] = df_b['answer'].apply(lambda x: x[:len(x)//2] + " (Truncated Naive)") # Giả lập baseline kém hơn
    
    final_results = []
    
    for i, row in df_a.iterrows():
        q = row['question']
        ans_a = row['answer']
        ans_b = df_b.iloc[i]['answer']
        ctx = row.get('contexts', "N/A")
        
        # Round 1: A vs B
        dec1 = get_judge_decision(q, ctx, ans_a, ans_b)
        
        # Round 2: B vs A (Swap to mitigate position bias)
        dec2_raw = get_judge_decision(q, ctx, ans_b, ans_a)
        dec2 = "A" if dec2_raw == "B" else ("B" if dec2_raw == "A" else "Tie")
        
        # Final Decision: Consistency check
        final_dec = dec1 if dec1 == dec2 else "Tie"
        
        final_results.append({
            "question": q,
            "version_a": ans_a,
            "version_b": ans_b,
            "decision": final_dec
        })
        
        if (i+1) % 5 == 0:
            print(f"  Judged {i+1}/{len(df_a)} questions...")

    # 3. Calculate Win Rates
    df_final = pd.DataFrame(final_results)
    total = len(df_final)
    win_a = len(df_final[df_final['decision'] == 'A'])
    win_b = len(df_final[df_final['decision'] == 'B'])
    ties = len(df_final[df_final['decision'] == 'Tie'])
    
    report = {
        "win_rate_a": round(win_a / total * 100, 2),
        "win_rate_b": round(win_b / total * 100, 2),
        "tie_rate": round(ties / total * 100, 2),
        "total_judged": total
    }
    
    os.makedirs("phase-b", exist_ok=True)
    df_final.to_csv("phase-b/pairwise_results.csv", index=False, encoding="utf-8-sig")
    with open("phase-b/judge_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ Pairwise Comparison Complete!")
    print(f"Version A Win Rate: {report['win_rate_a']}%")
    print(f"Version B Win Rate: {report['win_rate_b']}%")

if __name__ == "__main__":
    if not os.path.exists("phase-a/ragas_results.csv"):
        print("❌ Error: phase-a/ragas_results.csv not found. Run Phase A first.")
    else:
        run_pairwise_comparison()
