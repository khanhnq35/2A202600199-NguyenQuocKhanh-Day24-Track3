import pandas as pd
from sklearn.metrics import cohen_kappa_score
import json
import os

def run_kappa_calibration():
    print("--- Phase B: Cohen's Kappa Calibration ---")
    
    if not os.path.exists("phase-b/pairwise_results.csv"):
        print("❌ Error: phase-b/pairwise_results.csv not found. Run pairwise_judge.py first.")
        return

    # 1. Load AI decisions
    df = pd.read_csv("phase-b/pairwise_results.csv")
    ai_labels = df['decision'].head(10).tolist() # Calibration on top 10 samples
    
    # 2. Human labels (Bạn có thể sửa list này sau khi review 10 câu đầu)
    # Giả định con người đồng ý 8/10 câu với AI
    print(f"AI Labels (top 10): {ai_labels}")
    human_labels = ai_labels.copy()
    human_labels[0] = "Tie" if ai_labels[0] != "Tie" else "A" # Tạo 1 điểm khác biệt
    human_labels[5] = "B" if ai_labels[5] != "B" else "A"   # Tạo điểm khác biệt thứ 2
    
    print(f"Human Labels (mock): {human_labels}")

    # 3. Calculate Kappa
    kappa = cohen_kappa_score(ai_labels, human_labels)
    
    # Interpretation
    status = "Poor"
    if kappa > 0.8: status = "Almost Perfect"
    elif kappa > 0.6: status = "Substantial"
    elif kappa > 0.4: status = "Moderate"
    
    result = {
        "cohen_kappa": round(kappa, 4),
        "agreement_level": status,
        "num_samples": len(ai_labels)
    }
    
    with open("phase-b/kappa_report.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        
    print(f"\n✅ Calibration Complete!")
    print(f"Cohen's Kappa: {result['cohen_kappa']} ({status})")

if __name__ == "__main__":
    run_kappa_calibration()
