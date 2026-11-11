import pytest
from app.crawler import validate_url_safety, extract_internal_links

def test_validate_url_safety_ssrf():
    # Loopback
    safe, msg = validate_url_safety("http://127.0.0.1/admin")
    assert not safe
    assert "restricted" in msg or "127.0.0.1" in msg

    # Private IP
    safe, msg = validate_url_safety("http://192.168.1.1/secret")
    assert not safe

    # AWS metadata
    safe, msg = validate_url_safety("http://169.254.169.254/latest/meta-data/")
    assert not safe

    # Bad scheme
    safe, msg = validate_url_safety("ftp://example.com/file")
    assert not safe

    # Valid external public domain
    safe, _ = validate_url_safety("https://example.com")
    assert safe

def test_extract_internal_links():
    html = """
    <html>
      <body>
        <a href="/about">About Us</a>
        <a href="https://example.com/contact">Contact</a>
        <a href="https://external.org/blog">External</a>
        <a href="javascript:void(0)">Bad Link</a>
        <a href="/downloads/file.pdf">PDF file</a>
      </body>
    </html>
    """
    links = extract_internal_links(html, "https://example.com", "https://example.com")
    assert "https://example.com/about" in links
    assert "https://example.com/contact" in links
    assert "https://external.org/blog" not in links
    assert "https://example.com/downloads/file.pdf" not in links
