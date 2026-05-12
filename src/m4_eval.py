import os
import sys
import pandas as pd
import json
import re
import asyncio
from typing import Any, List, Optional, Dict

# Add root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import JUDGE_LLM
from src.utils import call_llm, get_embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_core.outputs import ChatResult, ChatGeneration, LLMResult, Generation
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper

class VertexChatModel(BaseChatModel):
    """Custom LangChain ChatModel for Vertex AI."""
    
    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs: Any) -> ChatResult:
        user_prompt = messages[-1].content
        system_prompt = messages[0].content if len(messages) > 1 else "Bạn là chuyên gia RAG."
        
        res = call_llm(system_prompt, user_prompt, model_name=JUDGE_LLM)
        
        # Clean JSON for Ragas
        match = re.search(r"(\{.*\})", res, re.DOTALL)
        clean_res = match.group(1) if match else res.strip()
        
        gen = ChatGeneration(message=AIMessage(content=clean_res))
        return ChatResult(generations=[gen])

    async def _agenerate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs: Any) -> ChatResult:
        return self._generate(messages, stop, **kwargs)

    def _llm_type(self) -> str:
        return "vertex-ai-custom"

class VertexEmbeddings(Embeddings):
    """Custom LangChain Embeddings for Vertex AI."""
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return get_embeddings(texts)

    def embed_query(self, text: str) -> List[float]:
        return get_embeddings([text])[0]
    
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embed_documents(texts)
    
    async def aembed_query(self, text: str) -> List[float]:
        return self.embed_query(text)

# Ragas wrappers for use in code
def get_ragas_llm():
    # Khởi tạo wrapper của Ragas bọc quanh ChatModel của chúng ta
    return LangchainLLMWrapper(VertexChatModel())

def get_ragas_embeddings():
    # Khởi tạo wrapper của Ragas bọc quanh Embeddings của chúng ta
    return LangchainEmbeddingsWrapper(VertexEmbeddings())

# --- Main Eval Function ---
def evaluate_ragas(questions: list[str], answers: list[str],
                   contexts: list[list[str]], ground_truths: list[str]) -> dict:
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from datasets import Dataset
    
    data = {
        "question": questions,
        "answer": answers,
        "contexts": contexts,
        "ground_truth": ground_truths
    }
    dataset = Dataset.from_dict(data)
    
    ragas_llm = get_ragas_llm()
    ragas_emb = get_ragas_embeddings()
    
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    
    results = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=ragas_llm,
        embeddings=ragas_emb
    )
    
    # Ragas results might need conversion
    res_dict = results.scores
    res_dict["per_question"] = results 
    return res_dict

def failure_analysis(eval_results, bottom_n=5):
    """Analyze lowest scoring samples."""
    df = eval_results.to_pandas()
    df['avg_score'] = df[['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']].mean(axis=1)
    
    bottom_df = df.sort_values(by='avg_score').head(bottom_n)
    
    failures = []
    for _, row in bottom_df.iterrows():
        worst_metric = row[['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']].idxmin()
        failures.append({
            "question": row['question'],
            "avg_score": row['avg_score'],
            "worst_metric": worst_metric,
            "diagnosis": "Low retrieval quality" if "context" in worst_metric else "LLM reasoning error",
            "suggested_fix": "Improve chunking" if "context" in worst_metric else "Refine prompt"
        })
    return failures

def load_test_set(path="phase-a/testset_v1.csv"):
    """Load test set from CSV or JSON."""
    if not os.path.exists(path):
        # Fallback to test_set.json if CSV not found
        path = "test_set.json"
        if not os.path.exists(path):
            return []
            
    if path.endswith(".csv"):
        df = pd.read_csv(path)
        return df.to_dict("records")
    elif path.endswith(".json"):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_report(results: Dict, failures: List[Dict], output_dir: str = "phase-a"):
    """Save evaluation results and failure analysis."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Save summary
    summary_path = os.path.join(output_dir, "ragas_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
        
    # Save failure analysis
    failure_path = os.path.join(output_dir, "failure_analysis.md")
    with open(failure_path, "w", encoding="utf-8") as f:
        f.write("# Failure Analysis\n\n")
        f.write("| Question | Avg Score | Worst Metric | Diagnosis | Fix |\n")
        f.write("|---|---|---|---|---|\n")
        for fail in failures:
            f.write(f"| {fail['question']} | {fail['avg_score']:.2f} | {fail['worst_metric']} | {fail['diagnosis']} | {fail['suggested_fix']} |\n")
