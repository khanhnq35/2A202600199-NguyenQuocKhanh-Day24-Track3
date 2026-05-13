import pandas as pd
from sklearn.metrics import cohen_kappa_score
import json
import os

def run_kappa_calibration():
    print("--- Phase B: Cohen's Kappa Calibration ---")
    
    if not os.path.exists("phase-b/pairwise_results.csv"):
        print("❌ Error: phase-b/pairwise_results.csv not found. Run pairwise_judge.py first.")
        return
    if not os.path.exists("phase-b/human_labels.csv"):
        print("❌ Error: phase-b/human_labels.csv not found. Add 10 human labels first.")
        return

    # 1. Load AI decisions and documented human labels
    df = pd.read_csv("phase-b/pairwise_results.csv")
    human_df = pd.read_csv("phase-b/human_labels.csv")
    ai_labels = df["winner_after_swap"].head(10).tolist()
    human_labels = human_df["human_label"].head(10).tolist()

    if len(human_labels) < 10:
        print(f"❌ Error: expected 10 human labels, found {len(human_labels)}.")
        return

    print(f"AI Labels (top 10): {ai_labels}")
    print(f"Human Labels: {human_labels}")

    kappa = cohen_kappa_score(ai_labels, human_labels)
    
    if kappa >= 0.8:
        status = "Almost Perfect"
    elif kappa >= 0.6:
        status = "Substantial"
    elif kappa >= 0.4:
        status = "Moderate"
    elif kappa >= 0.2:
        status = "Fair"
    elif kappa >= 0:
        status = "Slight"
    else:
        status = "Worse than chance"
    
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
