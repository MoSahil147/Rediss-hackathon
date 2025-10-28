import os
import numpy as np
import json
import pickle
from typing import Dict, Any, List
from scipy.spatial.distance import cosine

from redis import Redis
from sentence_transformers import SentenceTransformer


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
INVOICE_LIST_KEY = os.getenv("REDIS_INVOICE_LIST", "invoices_list")
DO_LIST_KEY = os.getenv("REDIS_DO_LIST", "dorag_list")
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
EMBED_DIM = int(os.getenv("EMBED_DIM", "384"))


_redis_client: Redis = None
_embedder: SentenceTransformer = None


def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = Redis.from_url(REDIS_URL, password=REDIS_PASSWORD, decode_responses=False)
    return _redis_client


def get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBED_MODEL)
    return _embedder


def upsert_invoice(doc_id: str, content: str, metadata: Dict[str, Any], embedding=None) -> None:
    """Store invoice in Redis as JSON with embedding"""
    r = get_redis()
    embedder = get_embedder()
    if embedding is None:
        embedding = embedder.encode([content])[0]
    
    doc_data = {
        "id": doc_id,
        "content": content,
        "metadata": metadata,
        "embedding": embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
    }
    
    # Store as JSON string
    r.lpush(INVOICE_LIST_KEY, json.dumps(doc_data))
    print(f"✓ Stored invoice {doc_id} in Redis")


def upsert_do(doc_id: str, content: str, metadata: Dict[str, Any], embedding=None) -> None:
    """Store DO in Redis as JSON with embedding"""
    r = get_redis()
    embedder = get_embedder()
    if embedding is None:
        embedding = embedder.encode([content])[0]
    
    doc_data = {
        "id": doc_id,
        "content": content,
        "metadata": metadata,
        "embedding": embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
    }
    
    # Store as JSON string
    r.lpush(DO_LIST_KEY, json.dumps(doc_data))
    print(f"✓ Stored DO {doc_id} in Redis")


def comparison_invoice(query_text: str, k: int = 3) -> Dict[str, Any]:
    """Find most similar invoices using cosine similarity"""
    try:
        r = get_redis()
        embedder = get_embedder()
        
        # Get query embedding
        query_embedding = embedder.encode([query_text])[0]
        
        # Get all invoices from Redis
        all_docs = r.lrange(INVOICE_LIST_KEY, 0, -1)
        
        if not all_docs:
            print(f"No documents found in Redis for key: {INVOICE_LIST_KEY}")
            return {"documents": [[]], "metadatas": [[]]}
        
        similarities = []
        for doc_bytes in all_docs:
            try:
                doc = json.loads(doc_bytes.decode('utf-8'))
                doc_embedding = np.array(doc['embedding'])
                similarity = 1 - cosine(query_embedding, doc_embedding)
                similarities.append({
                    'content': doc['content'],
                    'metadata': doc['metadata'],
                    'similarity': similarity
                })
            except Exception as e:
                print(f"Error processing doc: {e}")
                continue
        
        if not similarities:
            print("No valid documents found after processing")
            return {"documents": [[]], "metadatas": [[]]}
        
        # Sort by similarity and get top k
        similarities.sort(key=lambda x: x['similarity'], reverse=True)
        top_k = similarities[:k]
        
        # Format output like Chroma
        documents = []
        metadatas = []
        for item in top_k:
            documents.append(item['content'])
            metadatas.append(item['metadata'])
        
        return {
            "documents": [documents],
            "metadatas": [metadatas]
        }
    except Exception as e:
        print(f"Error in comparison_invoice: {e}")
        return {"documents": [[]], "metadatas": [[]]}


def rag_invoice_prompt_redis(new_ocr_text: str) -> str:
    """Build RAG prompt using Redis similarity search"""
    try:
        results = comparison_invoice(new_ocr_text, k=3)
        
        doc_txt = results['documents'][0][0] if results['documents'] and results['documents'][0] else ""
        doc_meta = results['metadatas'][0][0] if results['metadatas'] and results['metadatas'][0] else {}
        
        if doc_txt:
            prompt_rag = f"""
        Refer to the previous similar invoices:
        1. {doc_txt} (Fields: {doc_meta})

        Give dates in DD-MM-YYYY format
        NO explanations. JSON ONLY
        Return ContainerList and BankAccountDeatails as a List of Dicitonaries like json format
        Only Extract the same fields as in similar documents nothing extra

        The text to be analyzed from the document is below-
        {new_ocr_text}
    """
        else:
            # Fallback prompt if no similar documents found in Redis
            prompt_rag = f"""
        Extract key invoice information from the following document.

        Give dates in DD-MM-YYYY format
        NO explanations. JSON ONLY
        Return ContainerList and BankAccountDetails as a List of Dictionaries in JSON format

        The text to be analyzed from the document is below-
        {new_ocr_text}
    """
        return prompt_rag
    except Exception as e:
        print(f"Error in rag_invoice_prompt_redis: {e}")
        # Return a fallback prompt even if Redis fails
        return f"""
        Extract key invoice information from the following document.

        Give dates in DD-MM-YYYY format
        NO explanations. JSON ONLY
        Return ContainerList and BankAccountDetails as a List of Dictionaries in JSON format

        The text to be analyzed from the document is below-
        {new_ocr_text}
    """
