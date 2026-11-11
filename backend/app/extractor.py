import re
import hashlib
import logging
from typing import Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
from readability import Document as ReadabilityDoc
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

def compute_content_hash(text: str) -> str:
    cleaned = re.sub(r'\s+', ' ', text).strip()
    return hashlib.sha256(cleaned.encode('utf-8')).hexdigest()

def normalize_text(text: str) -> str:
    # Normalize unicode and whitespace
    text = re.sub(r'\r\n|\r', '\n', text)
    # Collapse multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Collapse multiple spaces on the same line
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def extract_from_html(html: str, url: str, fallback_title: Optional[str] = None) -> Tuple[str, str, list[str]]:
    soup = BeautifulSoup(html, 'html.parser')

    # Remove non-content tags before readability processing
    for tag in soup(['script', 'style', 'noscript', 'svg', 'iframe', 'form']):
        tag.decompose()

    # Extract headings
    headings = []
    for h in soup.find_all(['h1', 'h2', 'h3']):
        h_text = h.get_text(strip=True)
        if h_text and len(h_text) < 200:
            headings.append(h_text)
    headings = headings[:30]

    # Try readability
    title = fallback_title or ""
    clean_text = ""
    try:
        r_doc = ReadabilityDoc(str(soup))
        r_title = r_doc.title()
        if r_title and not title:
            title = r_title

        summary_html = r_doc.summary()
        summary_soup = BeautifulSoup(summary_html, 'html.parser')
        clean_text = summary_soup.get_text(separator='\n', strip=True)
    except Exception as e:
        logger.warning(f"Readability extraction error for {url}: {e}")

    # Fallback to direct soup text extraction if readability failed or returned too little
    if len(clean_text) < 50:
        # Also remove nav/footer/header for cleaner fallback
        for tag in soup(['nav', 'footer', 'header', 'aside']):
            tag.decompose()

        main_tag = soup.find(['main', 'article', '[role="main"]']) or soup.body or soup
        clean_text = main_tag.get_text(separator='\n', strip=True)

    if not title:
        title_tag = soup.find('title')
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
        elif headings:
            title = headings[0]
        else:
            title = url

    clean_text = normalize_text(clean_text)
    return title, clean_text, headings

def process_page_to_document(
    url: str,
    title: Optional[str] = None,
    text: Optional[str] = None,
    html: Optional[str] = None,
    scope_id: Optional[str] = None
) -> Document:
    headings = []
    final_title = title or ""
    final_text = ""

    if html:
        extracted_title, extracted_text, headings = extract_from_html(html, url, fallback_title=title)
        if not final_title:
            final_title = extracted_title
        final_text = extracted_text

    # If text was explicitly provided and longer/preferred, or if no html
    if text and (not final_text or len(text.strip()) > len(final_text)):
        final_text = normalize_text(text)

    if not final_title:
        final_title = url

    content_hash = compute_content_hash(final_text)

    # Prefix text with title and headings summary for better semantic grounding
    header_prefix = f"# {final_title}\n"
    if headings:
        header_prefix += f"Headings: {', '.join(headings[:10])}\n\n"
    full_content = header_prefix + final_text

    return Document(
        page_content=full_content,
        metadata={
            "scope_id": scope_id or "",
            "source_url": url,
            "page_title": final_title,
            "content_hash": content_hash,
            "raw_text_len": len(final_text),
        }
    )
