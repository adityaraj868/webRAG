import logging
from typing import Optional
from langchain_huggingface import HuggingFaceEmbeddings
from app.config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)

_embeddings_instance: Optional[HuggingFaceEmbeddings] = None

def get_embeddings() -> HuggingFaceEmbeddings:
    global _embeddings_instance
    if _embeddings_instance is None:
        logger.info(f"Loading HuggingFace embedding model: {EMBEDDING_MODEL}")
        _embeddings_instance = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
    return _embeddings_instance
