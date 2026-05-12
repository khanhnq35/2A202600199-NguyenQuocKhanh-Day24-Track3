import os
import sys
import pandas as pd
import json

# Add root to sys.path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.m4_eval import VertexChatModel, VertexEmbeddings
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from ragas.testset import TestsetGenerator
from ragas.llms import LangchainLLMWrapper
from ragas.embeddings import LangchainEmbeddingsWrapper
from config import DATA_DIR, TEST_SET_PATH

def generate_new_testset(target_size=30):
    print(f"--- Generating {target_size} new synthetic questions (Ragas 0.4.x API) ---")
    
    # 1. Load documents
    loader = DirectoryLoader(DATA_DIR, glob="*.md", loader_cls=TextLoader)
    documents = loader.load()
    print(f"Loaded {len(documents)} documents from {DATA_DIR}")

    if not documents:
        raise ValueError(f"No documents found in {DATA_DIR}")

    # 2. Initialize Ragas Generator with 0.4.x API
    # In 0.4.x, critic_llm is removed and embeddings is renamed to embedding_model
    generator = TestsetGenerator(
        llm=LangchainLLMWrapper(VertexChatModel()),
        embedding_model=LangchainEmbeddingsWrapper(VertexEmbeddings())
    )

    # 3. Generate with simplified 0.4.x approach
    try:
        testset = generator.generate_with_langchain_docs(
            documents, 
            testset_size=target_size
        )
        new_df = testset.to_pandas()
        
        # Standardize columns IMMEDIATELY
        column_map = {
            'user_input': 'question',
            'reference': 'ground_truth',
            'retrieved_contexts': 'contexts',
            'synthesizer_name': 'evolution_type'
        }
        new_df = new_df.rename(columns={k: v for k, v in column_map.items() if k in new_df.columns})
        
        return new_df
    except Exception as e:
        print(f"❌ Error inside generator: {e}")
        raise e

def merge_with_existing(new_df):
    print("--- Merging with existing 20 questions ---")
    
    # Load existing Day 18 test set
    with open(TEST_SET_PATH, "r", encoding="utf-8") as f:
        existing_data = json.load(f)
    
    existing_df = pd.DataFrame(existing_data)
    
    # Add evolution_type to existing (mostly simple)
    if 'evolution_type' not in existing_df.columns:
        existing_df['evolution_type'] = 'simple'
    
    # Standardize columns for Lab 24
    # Expected: question, ground_truth, contexts, evolution_type
    
    # Ragas 0.4.x columns might be: user_input (question), reference (ground_truth), retrieved_contexts (contexts), synthesizer_name (evolution_type)
    if 'user_input' in new_df.columns:
        new_df = new_df.rename(columns={
            'user_input': 'question',
            'reference': 'ground_truth',
            'retrieved_contexts': 'contexts',
            'synthesizer_name': 'evolution_type'
        })
    
    final_df = pd.concat([existing_df, new_df], ignore_index=True)
    return final_df

if __name__ == "__main__":
    try:
        # Create output dir
        os.makedirs("phase-a", exist_ok=True)
        
        # Run generation
        new_questions_df = generate_new_testset(30)
        
        # Merge
        final_testset = merge_with_existing(new_questions_df)
        
        # Save results
        output_path = "phase-a/testset_v1.csv"
        final_testset.to_csv(output_path, index=False, encoding="utf-8-sig")
        
        print(f"\n✅ Successfully generated and merged test set!")
        print(f"Total questions: {len(final_testset)}")
        print(f"Saved to: {output_path}")
        
    except Exception as e:
        print(f"❌ Error during generation: {e}")
        import traceback
        traceback.print_exc()
