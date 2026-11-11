import logging
from typing import List, Tuple, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.config import CHROMA_PERSIST_DIR
from app.embeddings import get_embeddings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "webrag_chunks"
_chroma_client: Optional[chromadb.PersistentClient] = None
_vectorstore_instance: Optional[Chroma] = None

def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
    return _chroma_client

def get_vectorstore() -> Chroma:
    global _vectorstore_instance
    if _vectorstore_instance is None:
        client = get_chroma_client()
        embeddings = get_embeddings()
        _vectorstore_instance = Chroma(
            client=client,
            collection_name=COLLECTION_NAME,
            embedding_function=embeddings,
        )
    return _vectorstore_instance

def add_documents_to_store(documents: List[Document]) -> List[str]:
    if not documents:
        return []
    vs = get_vectorstore()
    return vs.add_documents(documents)

def delete_documents_by_scope(scope_id: str) -> None:
    vs = get_vectorstore()
    try:
        vs._collection.delete(where={"scope_id": scope_id})
        logger.info(f"Deleted vector chunks for scope_id: {scope_id}")
    except Exception as e:
        logger.warning(f"Error deleting chunks for scope {scope_id}: {e}")

def delete_documents_by_url(scope_id: str, url: str) -> None:
    vs = get_vectorstore()
    try:
        vs._collection.delete(
            where={
                "$and": [
                    {"scope_id": scope_id},
                    {"source_url": url}
                ]
            }
        )
        logger.info(f"Deleted vector chunks for scope_id={scope_id}, url={url}")
    except Exception as e:
        logger.warning(f"Error deleting chunks for {url} in scope {scope_id}: {e}")

def similarity_search_scope(query: str, scope_id: str, k: int = 5) -> List[Tuple[Document, float]]:
    vs = get_vectorstore()
    # Enforce strict scope_id filtering to guarantee data isolation
    try:
        results = vs.similarity_search_with_relevance_scores(
            query=query,
            k=k,
            filter={"scope_id": scope_id}
        )
        return results
    except Exception as e:
        logger.error(f"Error querying Chroma for scope {scope_id}: {e}")
        return []

def get_all_chunks_by_scope(scope_id: str) -> List[Document]:
    vs = get_vectorstore()
    try:
        data = vs._collection.get(
            where={"scope_id": scope_id},
            include=["documents", "metadatas"]
        )
        texts = data.get("documents", []) or []
        metadatas = data.get("metadatas", []) or []
        docs = []
        for text, meta in zip(texts, metadatas):
            docs.append(Document(page_content=text, metadata=meta or {}))
        # Sort sequentially by source URL and chunk index
        docs.sort(key=lambda d: (d.metadata.get("source_url", ""), d.metadata.get("chunk_index", 0)))
        return docs
    except Exception as e:
        logger.error(f"Error fetching all chunks for scope {scope_id}: {e}")
        return []
