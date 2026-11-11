import logging
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.config import CHUNK_SIZE, CHUNK_OVERLAP

logger = logging.getLogger(__name__)

def split_document(document: Document, scope_id: str) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    raw_chunks = splitter.split_documents([document])
    processed_chunks: List[Document] = []

    for idx, chunk in enumerate(raw_chunks):
        meta = {
            "scope_id": scope_id,
            "source_url": document.metadata.get("source_url", ""),
            "page_title": document.metadata.get("page_title", ""),
            "chunk_index": idx,
            "content_hash": document.metadata.get("content_hash", ""),
        }
        processed_chunks.append(
            Document(
                page_content=chunk.page_content,
                metadata=meta
            )
        )

    logger.info(f"Split {document.metadata.get('source_url')} into {len(processed_chunks)} chunks for scope {scope_id}")
    return processed_chunks
