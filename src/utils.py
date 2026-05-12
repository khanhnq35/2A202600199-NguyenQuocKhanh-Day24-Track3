import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import (LLM_PROVIDER, DEFAULT_LLM, FALLBACK_LLM, GCP_PROJECT_ID, GCP_LOCATION,
                    EMBEDDING_PROVIDER, GCP_EMBEDDING_MODEL, 
                    EMBEDDING_DIM, EMBEDDING_MODEL)
from concurrent.futures import ThreadPoolExecutor

# Cache for models and init status
_vertex_init_done = False
_embedding_model = None

def call_llm(system_prompt: str, user_prompt: str, temperature: float = 0.0, model_name: str = None) -> str:
    """
    Hàm gọi LLM chung hỗ trợ cả GCP Vertex AI và OpenAI.
    
    Args:
        system_prompt: Nội dung system prompt.
        user_prompt: Nội dung user prompt.
        temperature: Độ sáng tạo của model (mặc định 0.0).
        
    Returns:
        Câu trả lời từ LLM hoặc chuỗi rỗng nếu có lỗi.
    """
    try:
        if LLM_PROVIDER == "google":
            import vertexai
            from vertexai.generative_models import GenerativeModel
            
            # Khởi tạo Vertex AI nếu project_id được cấu hình
            if GCP_PROJECT_ID:
                vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
            
            def generate_gemini(model_name):
                model = GenerativeModel(model_name)
                # Vertex AI không có role system riêng biệt theo cách OpenAI làm trong SDK đơn giản, 
                # gộp chung vào prompt hoặc dùng system_instruction nếu dùng SDK bản mới.
                # Ở đây gộp chung để đảm bảo tính tương thích cao.
                full_prompt = f"System: {system_prompt}\n\nUser: {user_prompt}"
                response = model.generate_content(full_prompt)
                return response.text

            target_model = model_name or DEFAULT_LLM
            try:
                return generate_gemini(target_model)
            except Exception as e:
                if model_name: # Nếu đã chỉ định model mà lỗi thì throw luôn hoặc handle riêng
                    print(f"Gemini {model_name} Error: {e}")
                    return ""
                print(f"Gemini Default Error: {e}, falling back to {FALLBACK_LLM}")
                return generate_gemini(FALLBACK_LLM)
        else:
            from openai import OpenAI
            client = OpenAI()
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            return resp.choices[0].message.content
    except Exception as e:
        print(f"LLM Error in utils.call_llm: {e}")
        return ""

def get_embeddings(texts: list[str], task: str = None) -> list[list[float]]:
    """
    Lấy embeddings hỗ trợ cả GCP Vertex AI (Native) và Local.
    """
    global _vertex_init_done, _embedding_model
    
    try:
        if EMBEDDING_PROVIDER == "google":
            import vertexai
            from vertexai.language_models import TextEmbeddingModel
            
            if not _vertex_init_done and GCP_PROJECT_ID:
                vertexai.init(project=GCP_PROJECT_ID, location=GCP_LOCATION)
                _vertex_init_done = True
            
            if _embedding_model is None:
                _embedding_model = TextEmbeddingModel.from_pretrained(GCP_EMBEDDING_MODEL)
            
            def get_batch_embeddings(batch):
                results = _embedding_model.get_embeddings(batch)
                return [r.values for r in results]

            batches = [texts[i:i+10] for i in range(0, len(texts), 10)]
            
            all_embeddings = []
            with ThreadPoolExecutor(max_workers=5) as executor:
                batch_results = list(executor.map(get_batch_embeddings, batches))
                for res in batch_results:
                    all_embeddings.extend(res)
            return all_embeddings
        else:
            # Chạy local dùng sentence-transformers
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(EMBEDDING_MODEL, trust_remote_code=True)
            return model.encode(texts).tolist()
    except Exception as e:
        print(f"Embedding Error in utils.get_embeddings: {e}")
        return [[0.0] * EMBEDDING_DIM] * len(texts)
