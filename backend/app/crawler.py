import os
import asyncio
import logging
import socket
import ipaddress
import xml.etree.ElementTree as ET
from urllib.parse import urlparse, urljoin, urldefrag
from urllib.robotparser import RobotFileParser
from typing import Set, List, Optional, Tuple, Callable
import httpx
from bs4 import BeautifulSoup

from app.config import (
    DEFAULT_MAX_CRAWL_PAGES,
    DEFAULT_MAX_CRAWL_DEPTH,
    DEFAULT_CRAWL_CONCURRENCY,
    REQUEST_TIMEOUT_SECONDS,
    ALLOW_LOCALHOST,
)
from app.database import update_crawl_job

logger = logging.getLogger(__name__)

USER_AGENT = "WebRAG-Crawler/1.0 (+https://github.com/webrag)"

def validate_url_safety(url: str, allow_localhost: Optional[bool] = None) -> Tuple[bool, str]:
    if allow_localhost is None:
        allow_localhost = os.getenv('ALLOW_LOCALHOST', 'false').lower() in ('true', '1')
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False, f"Unsupported scheme: {parsed.scheme}"

        hostname = parsed.hostname
        if not hostname:
            return False, "Missing hostname in URL"

        # Resolve IP addresses for hostname to prevent SSRF
        addr_infos = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_infos:
            ip = ipaddress.ip_address(sockaddr[0])
            if allow_localhost and ip.is_loopback:
                continue
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                return False, f"Target IP {ip} is restricted (SSRF protection)"

        return True, "Safe"
    except Exception as e:
        return False, f"URL validation failed: {str(e)}"

async def fetch_robots_parser(client: httpx.AsyncClient, origin: str) -> Optional[RobotFileParser]:
    robots_url = urljoin(origin, "/robots.txt")
    try:
        resp = await client.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=5.0)
        if resp.status_code == 200:
            parser = RobotFileParser()
            parser.parse(resp.text.splitlines())
            return parser
    except Exception as e:
        logger.debug(f"Could not load robots.txt for {origin}: {e}")
    return None

async def discover_sitemap_urls(client: httpx.AsyncClient, origin: str) -> List[str]:
    sitemap_url = urljoin(origin, "/sitemap.xml")
    found_urls: List[str] = []
    try:
        resp = await client.get(sitemap_url, headers={"User-Agent": USER_AGENT}, timeout=5.0)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            # Handle XML namespace if present
            for elem in root.iter():
                if elem.tag.endswith('loc') and elem.text:
                    loc = elem.text.strip()
                    if loc.startswith(origin):
                        clean_loc, _ = urldefrag(loc)
                        found_urls.append(clean_loc)
    except Exception as e:
        logger.debug(f"No valid sitemap found at {sitemap_url}: {e}")
    return found_urls

def extract_internal_links(html: str, current_url: str, base_origin: str) -> Set[str]:
    links: Set[str] = set()
    soup = BeautifulSoup(html, 'html.parser')
    for a in soup.find_all('a', href=True):
        raw_href = a['href'].strip()
        if not raw_href or raw_href.startswith(('javascript:', 'mailto:', 'tel:', '#')):
            continue

        resolved = urljoin(current_url, raw_href)
        clean_url, _ = urldefrag(resolved)

        parsed = urlparse(clean_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        # Restrict crawling strictly to same origin
        if origin.lower() == base_origin.lower():
            # Exclude media / static file extensions
            if not clean_url.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.gif', '.zip', '.tar', '.gz', '.mp4', '.mp3')):
                links.add(clean_url)
    return links

async def run_website_crawl(
    job_id: str,
    scope_id: str,
    base_url: str,
    max_pages: int = DEFAULT_MAX_CRAWL_PAGES,
    max_depth: int = DEFAULT_MAX_CRAWL_DEPTH,
    concurrency: int = DEFAULT_CRAWL_CONCURRENCY,
    on_page_extracted: Optional[Callable[[str, str, str], Any]] = None,
):
    update_crawl_job(job_id, status="running")

    is_safe, reason = validate_url_safety(base_url)
    if not is_safe:
        logger.error(f"Cannot crawl unsafe URL: {base_url} ({reason})")
        update_crawl_job(job_id, status="failed", error=reason)
        return

    parsed_base = urlparse(base_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

    clean_start_url, _ = urldefrag(base_url)
    visited: Set[str] = set()
    queue: List[Tuple[str, int]] = [(clean_start_url, 0)]
    discovered_urls: Set[str] = {clean_start_url}

    pages_crawled = 0
    pages_indexed = 0
    total_chunks = 0
    pages_failed = 0

    semaphore = asyncio.Semaphore(concurrency)

    limits = httpx.Limits(max_keepalive_connections=5, max_connections=concurrency)
    async with httpx.AsyncClient(limits=limits, follow_redirects=True, timeout=REQUEST_TIMEOUT_SECONDS) as client:
        # Check robots.txt
        robots_parser = await fetch_robots_parser(client, base_origin)

        # Check sitemap.xml for fast discovery
        sitemap_urls = await discover_sitemap_urls(client, base_origin)
        for s_url in sitemap_urls:
            if s_url not in discovered_urls:
                discovered_urls.add(s_url)
                queue.append((s_url, 1))

        async def process_url(url: str, depth: int):
            nonlocal pages_crawled, pages_indexed, total_chunks, pages_failed

            if pages_crawled >= max_pages:
                return

            if robots_parser and not robots_parser.can_fetch(USER_AGENT, url):
                logger.info(f"Skipping {url} (disallowed by robots.txt)")
                return

            # Re-validate safe destination (in case of odd hostnames)
            safe, err = validate_url_safety(url)
            if not safe:
                logger.warning(f"Skipping disallowed URL {url}: {err}")
                pages_failed += 1
                return

            update_crawl_job(
                job_id,
                current_url=url,
                pages_crawled=pages_crawled,
                pages_indexed=pages_indexed,
                total_chunks=total_chunks,
                pages_failed=pages_failed,
            )

            try:
                resp = await client.get(url, headers={"User-Agent": USER_AGENT})
                pages_crawled += 1

                if resp.status_code != 200:
                    logger.warning(f"Failed to fetch {url}: HTTP {resp.status_code}")
                    pages_failed += 1
                    return

                content_type = resp.headers.get("content-type", "")
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    return

                html_content = resp.text

                # Extract and index using the shared downstream pipeline
                if on_page_extracted:
                    chunks_added = await on_page_extracted(url, html_content, scope_id)
                    pages_indexed += 1
                    total_chunks += chunks_added

                # Discover new links if depth allows
                if depth < max_depth:
                    new_links = extract_internal_links(html_content, url, base_origin)
                    for n_link in new_links:
                        if n_link not in discovered_urls and len(queue) + pages_crawled < max_pages * 3:
                            discovered_urls.add(n_link)
                            queue.append((n_link, depth + 1))

            except Exception as e:
                logger.warning(f"Error crawling {url}: {e}")
                pages_failed += 1

        # BFS queue processing
        while queue and pages_crawled < max_pages:
            batch = []
            while queue and len(batch) < concurrency and (pages_crawled + len(batch)) < max_pages:
                next_item = queue.pop(0)
                if next_item[0] not in visited:
                    visited.add(next_item[0])
                    batch.append(next_item)

            if not batch:
                break

            tasks = [process_url(u, d) for u, d in batch]
            await asyncio.gather(*tasks)

    logger.info(f"Crawl job {job_id} finished. Crawled: {pages_crawled}, Indexed: {pages_indexed}, Chunks: {total_chunks}")
    update_crawl_job(
        job_id,
        status="completed",
        pages_crawled=pages_crawled,
        pages_indexed=pages_indexed,
        total_chunks=total_chunks,
        pages_failed=pages_failed,
        current_url=None,
    )
