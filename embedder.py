"""
embedder.py — shared embedding model singleton
Loaded once and reused across challenges.py and rag.py
"""

from langchain_huggingface import HuggingFaceEmbeddings

_embedder = None

def get_embedder() -> HuggingFaceEmbeddings:
    global _embedder
    if _embedder is None:
        _embedder = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
    return _embedder
