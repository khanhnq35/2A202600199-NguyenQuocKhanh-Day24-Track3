import os
import re
import json
import requests
from presidio_analyzer import AnalyzerEngine
from src.utils import call_llm

class PIIGuard:
    def __init__(self):
        self.analyzer = AnalyzerEngine()
        # Custom regex cho CCCD/MST Việt Nam
        self.vn_patterns = [
            {"name": "CCCD", "regex": r"\b\d{12}\b", "score": 0.9},
            {"name": "MST", "regex": r"\b\d{10}\b", "score": 0.8}
        ]

    def check(self, text: str) -> dict:
        results = self.analyzer.analyze(text=text, entities=[], language='en')
        
        # Check custom VN patterns
        found_pii = []
        for p in self.vn_patterns:
            if re.search(p["regex"], text):
                found_pii.append(p["name"])
        
        for res in results:
            found_pii.append(res.entity_type)
            
        is_safe = len(found_pii) == 0
        return {"safe": is_safe, "found": list(set(found_pii))}

class TopicGuard:
    def __init__(self, allowed_topics=["Pháp luật Việt Nam", "Nghị định 13", "Thuế GTGT", "Báo cáo tài chính"]):
        self.allowed_topics = allowed_topics

    def check(self, query: str) -> dict:
        prompt = f"""
        Phân loại câu hỏi sau có thuộc các chủ đề: {', '.join(self.allowed_topics)} hay không?
        Câu hỏi: "{query}"
        Trả về JSON: {{"is_on_topic": true/false, "reason": "ngắn gọn"}}
        """
        res = call_llm("Bạn là chuyên gia phân loại chủ đề.", prompt)
        try:
            # Clean JSON
            match = re.search(r"(\{.*\})", res, re.DOTALL)
            data = json.loads(match.group(1))
            return {"safe": data.get("is_on_topic", False), "reason": data.get("reason", "Unknown")}
        except:
            return {"safe": False, "reason": "Error parsing topic guard"}

class LlamaGuard:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def check(self, text: str) -> dict:
        if not self.api_key or self.api_key.startswith("gsk-..."):
            return {"safe": True, "reason": "Groq Key missing, skipping Llama Guard"}

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": "llama-guard-3-8b",
            "messages": [{"role": "user", "content": text}]
        }
        try:
            resp = requests.post(self.url, headers=headers, json=payload, timeout=10)
            res_text = resp.json()['choices'][0]['message']['content']
            is_safe = "unsafe" not in res_text.lower()
            return {"safe": is_safe, "reason": res_text if not is_safe else "Clear"}
        except Exception as e:
            return {"safe": True, "reason": f"Llama Guard Error: {e}"}

class GuardrailStack:
    def __init__(self):
        self.pii = PIIGuard()
        self.topic = TopicGuard()
        self.llama = LlamaGuard()

    def validate_input(self, query: str) -> dict:
        # L1: PII
        pii_res = self.pii.check(query)
        if not pii_res["safe"]:
            return {"safe": False, "layer": "PII", "message": f"Phát hiện thông tin nhạy cảm: {pii_res['found']}"}
        
        # L2: Topic
        topic_res = self.topic.check(query)
        if not topic_res["safe"]:
            return {"safe": False, "layer": "Topic", "message": f"Chủ đề không được phép: {topic_res['reason']}"}
            
        # L3: Llama Guard
        llama_res = self.llama.check(query)
        if not llama_res["safe"]:
            return {"safe": False, "layer": "LlamaGuard", "message": f"Nội dung vi phạm chính sách: {llama_res['reason']}"}

        return {"safe": True}
