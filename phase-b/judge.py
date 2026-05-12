"""Phase B: LLM-as-Judge — pairwise comparison + absolute scoring."""

import os
import sys
import json
import re
import time
import random
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import cohen_kappa_score

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import call_llm
from config import JUDGE_LLM

# ── Prompts ────────────────────────────────────────────────────────────────────

PAIRWISE_PROMPT = """Bạn là một chuyên gia đánh giá chất lượng câu trả lời hệ thống RAG.

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
{{"winner": "A" | "B" | "Tie", "reason": "<giải thích ngắn 1 câu>"}}
"""

ABSOLUTE_PROMPT = """Bạn là chuyên gia đánh giá hệ thống RAG tiếng Việt.

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
{{"accuracy": <1-5>, "relevance": <1-5>, "conciseness": <1-5>, "helpfulness": <1-5>, "reasoning": "<1 câu>"}}
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_winner(raw: str) -> str:
    """Robust JSON parse → winner label."""
    try:
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            w = data.get("winner", "Tie")
            if w in ("A", "B", "Tie"):
                return w
    except Exception:
        pass
    # Fallback: keyword scan
    if re.search(r"\bA\b", raw) and not re.search(r"\bB\b", raw):
        return "A"
    if re.search(r"\bB\b", raw) and not re.search(r"\bA\b", raw):
        return "B"
    return "Tie"


def _parse_scores(raw: str) -> dict:
    """Robust JSON parse → score dict."""
    default = {"accuracy": 3, "relevance": 3, "conciseness": 3, "helpfulness": 3, "reasoning": "parse error"}
    try:
        match = re.search(r"\{.*?\}", raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            for k in ("accuracy", "relevance", "conciseness", "helpfulness"):
                data[k] = max(1, min(5, int(data.get(k, 3))))
            return data
    except Exception:
        pass
    return default


# ── B.1 Pairwise Judge ─────────────────────────────────────────────────────────

def pairwise_judge_with_swap(question: str, context: str, answer_a: str, answer_b: str) -> dict:
    """Single pairwise comparison with position-bias swap."""
    # Run 1: A vs B
    p1 = PAIRWISE_PROMPT.format(question=question, context=context, answer_a=answer_a, answer_b=answer_b)
    raw1 = call_llm("Bạn là quan tòa trung lập.", p1, model_name=JUDGE_LLM)
    run1 = _parse_winner(raw1)

    # Run 2: B vs A (swapped)
    p2 = PAIRWISE_PROMPT.format(question=question, context=context, answer_a=answer_b, answer_b=answer_a)
    raw2 = call_llm("Bạn là quan tòa trung lập.", p2, model_name=JUDGE_LLM)
    run2_raw = _parse_winner(raw2)
    # Flip back to original labeling
    run2 = {"A": "B", "B": "A", "Tie": "Tie"}[run2_raw]

    # Consensus: agree → that winner; disagree → Tie
    winner_after_swap = run1 if run1 == run2 else "Tie"

    return {
        "run1_winner": run1,
        "run2_winner": run2,
        "winner_after_swap": winner_after_swap,
    }


def run_pairwise_comparison(results_a_path: str = "phase-a/ragas_results.csv",
                             n_questions: int = 30) -> pd.DataFrame:
    print("=== Phase B.1: Pairwise Judge (Swap-and-Average) ===")

    df_a = pd.read_csv(results_a_path)
    df_a = df_a.head(n_questions).reset_index(drop=True)

    records = []
    for i, row in df_a.iterrows():
        q = str(row.get("question", ""))
        ctx = str(row.get("contexts", ""))[:1000]
        answer_a = str(row.get("answer", ""))

        # Version B: naive baseline — truncate answer (simulates simpler retrieval)
        words = answer_a.split()
        answer_b = " ".join(words[:max(1, len(words) // 2)]) + " [Baseline: câu trả lời rút gọn]"

        result = pairwise_judge_with_swap(q, ctx, answer_a, answer_b)

        records.append({
            "question": q,
            "answer_a": answer_a,
            "answer_b": answer_b,
            "run1_winner": result["run1_winner"],
            "run2_winner": result["run2_winner"],
            "winner_after_swap": result["winner_after_swap"],
        })

        if (i + 1) % 5 == 0:
            print(f"  Judged {i+1}/{len(df_a)} ...")

    df_out = pd.DataFrame(records)
    os.makedirs("phase-b", exist_ok=True)
    df_out.to_csv("phase-b/pairwise_results.csv", index=False, encoding="utf-8-sig")

    # Summary
    total = len(df_out)
    win_a = (df_out["winner_after_swap"] == "A").sum()
    win_b = (df_out["winner_after_swap"] == "B").sum()
    ties  = (df_out["winner_after_swap"] == "Tie").sum()
    print(f"\nResults: A wins={win_a} ({win_a/total:.0%}), B wins={win_b} ({win_b/total:.0%}), Ties={ties} ({ties/total:.0%})")
    return df_out


# ── B.2 Absolute Scoring ───────────────────────────────────────────────────────

def absolute_score(question: str, context: str, answer: str, ground_truth: str) -> dict:
    """Score a single answer on 4 dimensions (1-5)."""
    prompt = ABSOLUTE_PROMPT.format(
        question=question, context=context, answer=answer, ground_truth=ground_truth
    )
    raw = call_llm("Bạn là chuyên gia đánh giá RAG.", prompt, model_name=JUDGE_LLM)
    scores = _parse_scores(raw)
    scores["overall"] = round(
        (scores["accuracy"] + scores["relevance"] + scores["conciseness"] + scores["helpfulness"]) / 4, 2
    )
    return scores


def run_absolute_scoring(results_a_path: str = "phase-a/ragas_results.csv",
                          n_questions: int = 30) -> pd.DataFrame:
    print("=== Phase B.2: Absolute Scoring ===")

    df = pd.read_csv(results_a_path).head(n_questions).reset_index(drop=True)
    records = []

    for i, row in df.iterrows():
        q   = str(row.get("question", ""))
        ctx = str(row.get("contexts", ""))[:1000]
        ans = str(row.get("answer", ""))
        gt  = str(row.get("ground_truth", ""))

        scores = absolute_score(q, ctx, ans, gt)
        records.append({"question": q, "answer": ans, **scores})

        if (i + 1) % 5 == 0:
            print(f"  Scored {i+1}/{len(df)} ...")

    df_out = pd.DataFrame(records)
    df_out.to_csv("phase-b/absolute_scores.csv", index=False, encoding="utf-8-sig")
    print(f"\nMean scores: {df_out[['accuracy','relevance','conciseness','helpfulness','overall']].mean().round(3).to_dict()}")
    return df_out


# ── B.3 Human Calibration + Cohen's Kappa ─────────────────────────────────────

def compute_kappa(pairwise_csv: str = "phase-b/pairwise_results.csv",
                  human_labels_csv: str = "phase-b/human_labels.csv") -> float:
    df_ai = pd.read_csv(pairwise_csv).head(10)
    df_human = pd.read_csv(human_labels_csv)

    ai_labels    = df_ai["winner_after_swap"].tolist()
    human_labels = df_human["human_label"].tolist()

    kappa = cohen_kappa_score(ai_labels, human_labels)
    level = (
        "Almost Perfect" if kappa > 0.8
        else "Substantial" if kappa > 0.6
        else "Moderate" if kappa > 0.4
        else "Fair" if kappa > 0.2
        else "Slight"
    )
    print(f"Cohen's Kappa: {kappa:.4f} → {level}")
    return kappa


# ── B.4 Bias Analysis ──────────────────────────────────────────────────────────

def analyze_bias(pairwise_csv: str = "phase-b/pairwise_results.csv") -> None:
    print("=== Phase B.4: Bias Analysis ===")
    df = pd.read_csv(pairwise_csv)

    os.makedirs("phase-b", exist_ok=True)

    # --- Position bias ---
    # In Run 1, A is always listed first. Count how often run1=A wins.
    pos_bias_rate = (df["run1_winner"] == "A").mean()
    print(f"Position bias (A listed first, wins): {pos_bias_rate:.1%} (expected ~50%)")

    # --- Length bias ---
    df["len_a"] = df["answer_a"].str.split().str.len()
    df["len_b"] = df["answer_b"].str.split().str.len()
    df["len_diff"] = df["len_a"] - df["len_b"]
    df["winner_numeric"] = df["winner_after_swap"].map({"A": 1, "B": -1, "Tie": 0})
    length_corr = df[["len_diff", "winner_numeric"]].corr().iloc[0, 1]
    print(f"Length-preference correlation: {length_corr:.4f}")

    # --- Chart ---
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Position bias bar
    run1_counts = df["run1_winner"].value_counts()
    axes[0].bar(run1_counts.index, run1_counts.values, color=["#4C72B0", "#DD8452", "#55A868"])
    axes[0].axhline(len(df) / 3, color="red", linestyle="--", label="Expected (no bias)")
    axes[0].set_title("Position Bias: Run-1 Winners\n(A always listed first)")
    axes[0].set_ylabel("Count")
    axes[0].legend()
    for bar, val in zip(axes[0].patches, run1_counts.values):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                     f"{val/len(df):.0%}", ha="center")

    # Length bias scatter
    colors = df["winner_after_swap"].map({"A": "#4C72B0", "B": "#DD8452", "Tie": "#55A868"})
    axes[1].scatter(df["len_diff"], df["winner_numeric"], c=colors, alpha=0.6)
    z = np.polyfit(df["len_diff"].dropna(), df["winner_numeric"].dropna(), 1)
    p = np.poly1d(z)
    x_range = np.linspace(df["len_diff"].min(), df["len_diff"].max(), 100)
    axes[1].plot(x_range, p(x_range), "r--", label=f"Trend (r={length_corr:.2f})")
    axes[1].axhline(0, color="gray", linestyle=":", alpha=0.5)
    axes[1].set_title("Length Bias: Answer Length Difference vs Judge Preference")
    axes[1].set_xlabel("len(A) - len(B) in words")
    axes[1].set_ylabel("Judge preference (A=1, Tie=0, B=-1)")
    axes[1].legend()

    plt.tight_layout()
    plt.savefig("phase-b/bias_analysis.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("Saved: phase-b/bias_analysis.png")

    # --- Report ---
    report_lines = [
        "# Judge Bias Observations Report\n",
        "## 1. Position Bias\n",
        f"- **Rate A wins when listed first (Run 1):** {pos_bias_rate:.1%}",
        f"- Expected (no bias): ~33% (3-class: A / B / Tie)",
        f"- **Assessment:** {'⚠️ Significant bias detected (>40%)' if pos_bias_rate > 0.4 else '✅ Acceptable — within noise range'}",
        "",
        "**Mitigation (already applied):** Swap-and-average — judge each pair twice with A↔B swapped;",
        "only count win if consistent across both orderings. Inconsistent → Tie.",
        "",
        "## 2. Length Bias\n",
        f"- **Pearson correlation (len_diff vs judge preference):** {length_corr:.4f}",
        f"- {'⚠️ Positive correlation: judge prefers longer answers' if length_corr > 0.2 else '✅ Low length bias'}",
        "",
        "**Mitigation strategy:**",
        "- Add explicit rubric criterion: 'Penalise padding and repetition'",
        "- In prompt, instruct judge: 'Do not favour longer answers unless extra length adds substance'",
        "- Monitor `conciseness` dimension from absolute scoring as independent signal",
        "",
        "## 3. Chart\n",
        "![Bias Analysis](bias_analysis.png)\n",
        "## 4. Summary\n",
        "| Bias Type | Magnitude | Mitigated? |",
        "|---|---|---|",
        f"| Position bias | {pos_bias_rate:.1%} A-first wins | Yes — swap-and-average |",
        f"| Length bias | r={length_corr:.3f} | Partial — rubric instruction |",
    ]

    with open("phase-b/judge_bias_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    print("Saved: phase-b/judge_bias_report.md")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["pairwise", "absolute", "kappa", "bias", "all"],
                        default="all")
    args = parser.parse_args()

    ragas_csv = "phase-a/ragas_results.csv"
    if not os.path.exists(ragas_csv):
        print(f"ERROR: {ragas_csv} not found. Run Phase A first.")
        sys.exit(1)

    if args.task in ("pairwise", "all"):
        run_pairwise_comparison(ragas_csv)

    if args.task in ("absolute", "all"):
        run_absolute_scoring(ragas_csv)

    if args.task in ("bias", "all") and os.path.exists("phase-b/pairwise_results.csv"):
        analyze_bias()

    if args.task in ("kappa", "all") and os.path.exists("phase-b/human_labels.csv"):
        compute_kappa()
