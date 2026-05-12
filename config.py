"""Shared configuration for Lab 18."""

import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
COHERE_API_KEY = os.getenv("COHERE_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# --- GCP Vertex AI ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCP_LOCATION = os.getenv("GCP_LOCATION", "us-central1")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "google")  # "google" or "openai"
DEFAULT_LLM = os.getenv("DEFAULT_LLM", "gemini-2.5-pro")
FALLBACK_LLM = os.getenv("FALLBACK_LLM", "gemini-2.5-flash")
JUDGE_LLM = os.getenv("JUDGE_LLM", "gemini-2.5-pro")

# --- Embedding Provider ---
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "google") # "google" (Vertex AI) or "local"
GCP_EMBEDDING_MODEL = os.getenv("GCP_EMBEDDING_MODEL", "text-embedding-004") # Model native của Google

# --- Qdrant ---
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "lab18_production"
NAIVE_COLLECTION = "lab18_naive"

# --- Embedding ---
# Default to Vertex AI text-embedding-004
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
EMBEDDING_DIM = 768  # text-embedding-004 output dimension

# --- Chunking ---
HIERARCHICAL_PARENT_SIZE = 2048
HIERARCHICAL_CHILD_SIZE = 256
SEMANTIC_THRESHOLD = 0.85

# --- Search ---
BM25_TOP_K = 50
DENSE_TOP_K = 50
HYBRID_TOP_K = 50
RERANK_TOP_K = 10

# --- Paths ---
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
TEST_SET_PATH = os.path.join(os.path.dirname(__file__), "test_set.json")
