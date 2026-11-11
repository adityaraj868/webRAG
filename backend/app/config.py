import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root or backend directory
env_path = Path(__file__).resolve().parent.parent / '.env'
if not env_path.exists():
    env_path = Path(__file__).resolve().parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
DATA_DIR.mkdir(parents=True, exist_ok=True)

def get_groq_api_key() -> str:
    # 1. Process environment variable takes precedence if explicitly set
    if "GROQ_API_KEY" in os.environ:
        k = os.environ["GROQ_API_KEY"].strip()
        if k != "your_groq_api_key_here":
            return k
        return ""
    # 2. Check env file on disk dynamically so editing backend/.env works without server restart
    if env_path.exists():
        try:
            from dotenv import dotenv_values
            vals = dotenv_values(env_path)
            file_key = (vals.get('GROQ_API_KEY') or '').strip()
            if file_key and file_key != 'your_groq_api_key_here':
                return file_key
        except Exception:
            pass
    return ""

def get_groq_model() -> str:
    # 1. Process environment variable takes precedence
    if "GROQ_MODEL" in os.environ:
        m = os.environ["GROQ_MODEL"].strip()
        if m:
            return m
    # 2. Check env file on disk
    if env_path.exists():
        try:
            from dotenv import dotenv_values
            vals = dotenv_values(env_path)
            model = (vals.get('GROQ_MODEL') or '').strip()
            if model:
                return model
        except Exception:
            pass
    return "openai/gpt-oss-120b"

def get_groq_fallback_model() -> str:
    # 1. Process environment variable takes precedence
    if "GROQ_FALLBACK_MODEL" in os.environ:
        m = os.environ["GROQ_FALLBACK_MODEL"].strip()
        if m:
            return m
    # 2. Check env file on disk
    if env_path.exists():
        try:
            from dotenv import dotenv_values
            vals = dotenv_values(env_path)
            fallback = (vals.get('GROQ_FALLBACK_MODEL') or '').strip()
            if fallback:
                return fallback
        except Exception:
            pass
    return "openai/gpt-oss-20b"

GROQ_API_KEY = get_groq_api_key()
GROQ_MODEL = get_groq_model()
GROQ_FALLBACK_MODEL = get_groq_fallback_model()
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')

CHROMA_PERSIST_DIR = os.getenv('CHROMA_PERSIST_DIR', str(DATA_DIR / 'chroma'))
SQLITE_DB_PATH = os.getenv('SQLITE_DB_PATH', str(DATA_DIR / 'webrag.db'))

DEFAULT_MAX_CRAWL_PAGES = int(os.getenv('DEFAULT_MAX_CRAWL_PAGES', '10'))
DEFAULT_MAX_CRAWL_DEPTH = int(os.getenv('DEFAULT_MAX_CRAWL_DEPTH', '2'))
DEFAULT_CRAWL_CONCURRENCY = int(os.getenv('DEFAULT_CRAWL_CONCURRENCY', '2'))
REQUEST_TIMEOUT_SECONDS = int(os.getenv('REQUEST_TIMEOUT_SECONDS', '10'))
ALLOW_LOCALHOST = os.getenv('ALLOW_LOCALHOST', 'false').lower() in ('true', '1')

CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '1000'))
CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '200'))
DEFAULT_TOP_K = int(os.getenv('DEFAULT_TOP_K', '5'))

# Token Budget & Context Window Management
MODEL_CONTEXT_WINDOW = int(os.getenv('MODEL_CONTEXT_WINDOW', '131072'))
SAFETY_MARGIN_TOKENS = int(os.getenv('SAFETY_MARGIN_TOKENS', '4096'))
EXPECTED_COMPLETION_TOKENS = int(os.getenv('EXPECTED_COMPLETION_TOKENS', '4096'))
SUMMARIZATION_BATCH_TOKEN_LIMIT = int(os.getenv('SUMMARIZATION_BATCH_TOKEN_LIMIT', '6000'))
SUMMARIZATION_REDUCE_FAN_IN = int(os.getenv('SUMMARIZATION_REDUCE_FAN_IN', '6'))
SUMMARIZATION_RATE_DELAY = float(os.getenv('SUMMARIZATION_RATE_DELAY', '0.2'))

# Groq Resilience and Backoff
GROQ_MAX_RETRIES = int(os.getenv('GROQ_MAX_RETRIES', '3'))
GROQ_RETRY_BASE_DELAY = float(os.getenv('GROQ_RETRY_BASE_DELAY', '1.0'))
GROQ_MAX_RETRY_DELAY = float(os.getenv('GROQ_MAX_RETRY_DELAY', '10.0'))
