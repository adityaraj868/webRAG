import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path
from app.config import SQLITE_DB_PATH

logger = logging.getLogger(__name__)

def get_db_connection() -> sqlite3.Connection:
    Path(SQLITE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(SQLITE_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scopes (
                    scope_id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    base_url TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    indexed_at TEXT NOT NULL,
                    UNIQUE(scope_id, url),
                    FOREIGN KEY (scope_id) REFERENCES scopes(scope_id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    citations_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (scope_id) REFERENCES scopes(scope_id) ON DELETE CASCADE
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crawl_jobs (
                    job_id TEXT PRIMARY KEY,
                    scope_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pages_crawled INTEGER NOT NULL DEFAULT 0,
                    pages_indexed INTEGER NOT NULL DEFAULT 0,
                    total_chunks INTEGER NOT NULL DEFAULT 0,
                    pages_failed INTEGER NOT NULL DEFAULT 0,
                    current_url TEXT,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (scope_id) REFERENCES scopes(scope_id) ON DELETE CASCADE
                )
            """)
            try:
                conn.execute("ALTER TABLE crawl_jobs ADD COLUMN pages_failed INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass
    finally:
        conn.close()

def upsert_scope(scope_id: str, scope_type: str, base_url: str):
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
                INSERT INTO scopes (scope_id, type, base_url, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(scope_id) DO UPDATE SET
                    type = excluded.type,
                    base_url = excluded.base_url
            """, (scope_id, scope_type, base_url, now))
    finally:
        conn.close()

def get_scope(scope_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM scopes WHERE scope_id = ?", (scope_id,))
        row = cur.fetchone()
        if not row:
            return None
        return dict(row)
    finally:
        conn.close()

def delete_scope_metadata(scope_id: str) -> bool:
    conn = get_db_connection()
    try:
        with conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM messages WHERE scope_id = ?", (scope_id,))
            cur.execute("DELETE FROM documents WHERE scope_id = ?", (scope_id,))
            cur.execute("DELETE FROM crawl_jobs WHERE scope_id = ?", (scope_id,))
            cur.execute("DELETE FROM scopes WHERE scope_id = ?", (scope_id,))
            return cur.rowcount > 0
    finally:
        conn.close()

def get_document_hash(scope_id: str, url: str) -> Optional[str]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT content_hash FROM documents WHERE scope_id = ? AND url = ?",
            (scope_id, url)
        )
        row = cur.fetchone()
        return row["content_hash"] if row else None
    finally:
        conn.close()

def record_document(scope_id: str, url: str, title: str, content_hash: str, chunk_count: int):
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
                INSERT INTO documents (scope_id, url, title, content_hash, chunk_count, indexed_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(scope_id, url) DO UPDATE SET
                    title = excluded.title,
                    content_hash = excluded.content_hash,
                    chunk_count = excluded.chunk_count,
                    indexed_at = excluded.indexed_at
            """, (scope_id, url, title, content_hash, chunk_count, now))
    finally:
        conn.close()

def get_scope_documents(scope_id: str) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT url, title, chunk_count, content_hash, indexed_at
            FROM documents WHERE scope_id = ? ORDER BY indexed_at ASC
        """, (scope_id,))
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

def create_crawl_job(job_id: str, scope_id: str):
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
                INSERT INTO crawl_jobs (job_id, scope_id, status, pages_crawled, pages_indexed, total_chunks, created_at, updated_at)
                VALUES (?, ?, 'pending', 0, 0, 0, ?, ?)
            """, (job_id, scope_id, now, now))
    finally:
        conn.close()

def update_crawl_job(
    job_id: str,
    status: Optional[str] = None,
    pages_crawled: Optional[int] = None,
    pages_indexed: Optional[int] = None,
    total_chunks: Optional[int] = None,
    pages_failed: Optional[int] = None,
    current_url: Optional[str] = None,
    error: Optional[str] = None,
):
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    updates = ["updated_at = ?"]
    params: List[Any] = [now]

    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if pages_crawled is not None:
        updates.append("pages_crawled = ?")
        params.append(pages_crawled)
    if pages_indexed is not None:
        updates.append("pages_indexed = ?")
        params.append(pages_indexed)
    if total_chunks is not None:
        updates.append("total_chunks = ?")
        params.append(total_chunks)
    if pages_failed is not None:
        updates.append("pages_failed = ?")
        params.append(pages_failed)
    if current_url is not None:
        updates.append("current_url = ?")
        params.append(current_url)
    if error is not None:
        updates.append("error = ?")
        params.append(error)

    params.append(job_id)
    sql = f"UPDATE crawl_jobs SET {', '.join(updates)} WHERE job_id = ?"
    try:
        with conn:
            conn.execute(sql, tuple(params))
    finally:
        conn.close()

def get_crawl_job(job_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM crawl_jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def save_chat_message(scope_id: str, role: str, content: str, citations: Optional[List[Dict[str, Any]]] = None):
    conn = get_db_connection()
    now = datetime.now(timezone.utc).isoformat()
    cit_json = json.dumps(citations or [])
    try:
        with conn:
            conn.execute("""
                INSERT INTO messages (scope_id, role, content, citations_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (scope_id, role, content, cit_json, now))
    finally:
        conn.close()

def get_chat_history(scope_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT role, content, citations_json, created_at
            FROM (
                SELECT id, role, content, citations_json, created_at
                FROM messages WHERE scope_id = ?
                ORDER BY id DESC LIMIT ?
            )
            ORDER BY id ASC
        """, (scope_id, limit))
        rows = cur.fetchall()
        messages = []
        for r in rows:
            cit = []
            if r["citations_json"]:
                try:
                    cit = json.loads(r["citations_json"])
                except Exception:
                    cit = []
            messages.append({
                "role": r["role"],
                "content": r["content"],
                "citations": cit,
                "created_at": r["created_at"],
            })
        return messages
    finally:
        conn.close()
