import os
import sys
import pandas as pd
import json
import time

# Add root to sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pipeline import build_pipeline, run_query
from src.m4_eval import evaluate_ragas, failure_analysis, save_report

def run_full_evaluation(input_csv="phase-a/testset_v1.csv"):
    print(f"--- Starting Full RAGAS Evaluation on {input_csv} ---")
    start_time = time.time()
    
    # 1. Load Test Set
    df = pd.read_csv(input_csv)
    print(f"Loaded {len(df)} questions.")

    # 2. Build Pipeline
    search, reranker, parent_lookup = build_pipeline()

    # 3. Get Answers from RAG Pipeline
    print("\n[1/3] Generating answers from RAG pipeline...")
    questions = df['question'].tolist()
    ground_truths = df['ground_truth'].tolist()
    
    answers = []
    all_contexts = []
    
    for i, q in enumerate(questions):
        ans, ctx = run_query(q, search, reranker, parent_lookup)
        answers.append(ans)
        all_contexts.append(ctx)
        if (i+1) % 5 == 0:
            print(f"  Processed {i+1}/{len(questions)} questions...")

    # 4. Run RAGAS
    print("\n[2/3] Running RAGAS Evaluation (4 metrics)...")
    results = evaluate_ragas(questions, answers, all_contexts, ground_truths)

    # 5. Export Results
    print("\n[3/3] Exporting reports...")
    
    # Create results dataframe
    per_q = results.pop("per_question") # This contains EvalResult objects
    
    detailed_results = []
    for res in per_q:
        detailed_results.append({
            "question": res.question,
            "answer": res.answer,
            "ground_truth": res.ground_truth,
            "faithfulness": res.faithfulness,
            "answer_relevancy": res.answer_relevancy,
            "context_precision": res.context_precision,
            "context_recall": res.context_recall
        })
    
    results_df = pd.DataFrame(detailed_results)
    results_df.to_csv("phase-a/ragas_results.csv", index=False, encoding="utf-8-sig")
    
    # Export summary
    summary = {
        "aggregate_scores": results,
        "total_questions": len(questions),
        "execution_time_seconds": round(time.time() - start_time, 2)
    }
    with open("phase-a/ragas_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 6. Failure Analysis
    print("\n--- Failure Analysis (Bottom 10) ---")
    failures = failure_analysis(per_q, bottom_n=10)
    
    # Save failure analysis to markdown
    with open("phase-a/failure_analysis.md", "w", encoding="utf-8") as f:
        f.write("# Failure Cluster Analysis\n\n")
        f.write("## Bottom 10 Questions\n\n")
        f.write("| Question | Avg Score | Worst Metric | Diagnosis | Fix |\n")
        f.write("|---|---|---|---|---|\n")
        for fail in failures:
            f.write(f"| {fail['question'][:50]}... | {fail['avg_score']:.2f} | {fail['worst_metric']} | {fail['diagnosis']} | {fail['suggested_fix']} |\n")
        
        f.write("\n## Clusters & Patterns\n\n")
        f.write("### Cluster 1: [Tên Cluster, VD: Hallucination]\n")
        f.write("- **Pattern**: ...\n")
        f.write("- **Examples**: ...\n")
        f.write("- **Root Cause**: ...\n")
        f.write("- **Proposed Fix**: ...\n")

    print(f"\n✅ Evaluation complete! Total time: {summary['execution_time_seconds']}s")
    print("Files created in phase-a/: ragas_results.csv, ragas_summary.json, failure_analysis.md")

if __name__ == "__main__":
    if not os.path.exists("phase-a/testset_v1.csv"):
        print("❌ Error: phase-a/testset_v1.csv not found. Run generate_testset.py first.")
    else:
        run_full_evaluation()
