"""CI/CD evaluation gate — fails with exit code 1 if any metric below threshold."""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.m4_eval import evaluate_ragas, failure_analysis, load_test_set
from src.pipeline import build_pipeline, run_query

THRESHOLDS = {
    "faithfulness": 0.75,
    "answer_relevancy": 0.70,
    "context_precision": 0.60,
    "context_recall": 0.65,
}

def main():
    print("=== RAG Evaluation Gate ===")

    test_data = load_test_set("phase-a/testset_v1.csv")
    if not test_data:
        print("ERROR: No test data found. Ensure phase-a/testset_v1.csv exists.")
        sys.exit(1)

    search, reranker, parent_lookup = build_pipeline()

    questions, answers, contexts, ground_truths = [], [], [], []
    for item in test_data:
        q = item["question"]
        gt = item.get("ground_truth", "")
        ans, ctx = run_query(q, search, reranker, parent_lookup)
        questions.append(q)
        answers.append(ans)
        contexts.append(ctx)
        ground_truths.append(gt)

    results = evaluate_ragas(questions, answers, contexts, ground_truths)
    per_q = results.pop("per_question", None)

    print("\n--- Results ---")
    failed_metrics = []
    for metric, threshold in THRESHOLDS.items():
        score = results.get(metric, 0.0)
        status = "PASS" if score >= threshold else "FAIL"
        print(f"  {metric}: {score:.4f} (threshold={threshold}) [{status}]")
        if score < threshold:
            failed_metrics.append(metric)

    os.makedirs("phase-a", exist_ok=True)
    with open("phase-a/ragas_summary.json", "w", encoding="utf-8") as f:
        json.dump({"aggregate_scores": results, "thresholds": THRESHOLDS}, f, indent=2)

    if failed_metrics:
        print(f"\nGATE FAILED: metrics below threshold: {failed_metrics}")
        sys.exit(1)
    else:
        print("\nGATE PASSED: all metrics above threshold.")
        sys.exit(0)


if __name__ == "__main__":
    main()
