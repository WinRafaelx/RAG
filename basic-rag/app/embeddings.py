import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

import threading

_openai_client = None
_local_model = None
_model_lock = threading.Lock()

def get_embedding(text: str, is_query: bool = False) -> list[float]:
    provider = os.getenv("EMBEDDING_PROVIDER", "local").lower()
    model_name = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    
    cleaned_text = text.replace("\n", " ").strip()
    
    if provider == "openai":
        global _openai_client
        if _openai_client is None:
            _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = _openai_client.embeddings.create(
            input=[cleaned_text],
            model=model_name
        )
        return response.data[0].embedding
        
    elif provider == "local":
        global _local_model
        if _local_model is None:
            with _model_lock:
                if _local_model is None:
                    from sentence_transformers import SentenceTransformer
                    _local_model = SentenceTransformer(model_name)
            
        # e5 models recommend prefixing queries with "query: " and passages with "passage: "
        if "e5" in model_name.lower():
            prefix = "query: " if is_query else "passage: "
            if not cleaned_text.startswith(prefix):
                cleaned_text = prefix + cleaned_text
                
        embedding = _local_model.encode(cleaned_text)
        return list(map(float, embedding))
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")
