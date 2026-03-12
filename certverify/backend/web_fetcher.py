"""
Web Fetcher — 3-layer strategy:

  Layer 1: requests + BeautifulSoup (fast, no browser)
           -> If 403/blocked -> Layer 2

  Layer 2: Playwright headless Chromium screenshot + OCR
           -> Real browser, renders JS, takes screenshot, OCRs it

  Layer 3: Extract cert ID from URL + try platform API
           -> Udemy UUID format UC-xxxx-xxxx-xxxx-xxxx now supported
"""

import re
import time
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

import browser_fetcher


def _session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        ),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection":      "keep-alive",
        "Cache-Control":   "no-cache",
    })
    return s


# ============================================================================
#  Public entry point
# ============================================================================

def fetch_certificate_from_url(url: str) -> str:
    url = url.strip()
    if not url.startswith("http"):
        url = "https://" + url

    domain = urlparse(url).netloc.lower()
    print(f"[web_fetcher] url={url}")

    # Layer 1: fast requests
    print("[web_fetcher] Layer 1: trying requests...")
    try:
        text = _fetch_requests(url, domain)
        if text and len(text.strip()) > 50:
            print(f"[web_fetcher] Layer 1 SUCCESS — {len(text)} chars")
            return text
        print("[web_fetcher] Layer 1: too little content")
    except BlockedError as e:
        print(f"[web_fetcher] Layer 1 BLOCKED: {e}")
    except Exception as e:
        print(f"[web_fetcher] Layer 1 failed: {e}")

    # Layer 2: headless browser + OCR
    if browser_fetcher.is_available():
        print("[web_fetcher] Layer 2: launching headless browser...")
        try:
            result = browser_fetcher.fetch_with_browser(url)
            text = result.get("text", "")
            if text and len(text.strip()) > 50:
                print(f"[web_fetcher] Layer 2 SUCCESS — {len(text)} chars")
                return text
            print("[web_fetcher] Layer 2: too little content")
        except Exception as e:
            print(f"[web_fetcher] Layer 2 failed: {e}")
    else:
        print("[web_fetcher] Layer 2: Playwright not installed — skipping")
        print("  To enable: pip install playwright && playwright install chromium")

    # Layer 3: ID extraction + platform API
    print("[web_fetcher] Layer 3: extracting cert ID from URL")
    fallback = _id_from_url(url, domain)
    if fallback:
        print("[web_fetcher] Layer 3: returning ID-based fallback")
        return fallback

    raise RuntimeError(
        "Could not fetch certificate data.\n\n"
        "Fix options:\n"
        "1. Install Playwright (enables real browser screenshot):\n"
        "   pip install playwright\n"
        "   playwright install chromium\n\n"
        "2. Use 'Paste official text manually' option in the UI."
    )


# ============================================================================
#  Layer 1 — requests
# ============================================================================

class BlockedError(Exception):
    pass


def _fetch_requests(url: str, domain: str) -> str:
    if not REQUESTS_AVAILABLE:
        raise RuntimeError("requests not installed")

    session = _session()

    for attempt in range(2):
        try:
            resp = session.get(url, timeout=20, allow_redirects=True, verify=True)
            print(f"[requests] status={resp.status_code}")

            if resp.status_code == 200:
                return _parse_html(resp.text, domain)
            elif resp.status_code in (403, 401):
                raise BlockedError(f"HTTP {resp.status_code} — platform blocked the request")
            elif resp.status_code == 404:
                raise RuntimeError("HTTP 404 — certificate page not found. Check the URL.")
            elif resp.status_code == 429:
                time.sleep(3)
                continue
            else:
                raise RuntimeError(f"HTTP {resp.status_code}")

        except (BlockedError, RuntimeError):
            raise
        except requests.exceptions.SSLError:
            try:
                resp = session.get(url, timeout=20, verify=False)
                if resp.status_code == 200:
                    return _parse_html(resp.text, domain)
            except Exception:
                pass
            raise RuntimeError("SSL error")
        except requests.exceptions.ConnectionError:
            if attempt == 1:
                raise RuntimeError("Connection refused — check your internet connection")
            time.sleep(2)
        except requests.exceptions.Timeout:
            raise RuntimeError("Request timed out")

    raise RuntimeError("requests failed after retries")


def _parse_html(html: str, domain: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer",
                     "header", "aside", "noscript", "iframe"]):
        tag.decompose()

    if "nptel.ac.in" in domain or "swayam" in domain:
        selectors = ["table", "td", "th", "[class*='cert']",
                     "[class*='result']", "h1", "h2", "p"]
        parts = _collect(soup, selectors, 80)
        if parts:
            return parts

    body = soup.find("body")
    if not body:
        return ""
    raw = body.get_text("\n", strip=True)
    lines = [l.strip() for l in raw.splitlines()
             if len(l.strip()) > 4 and re.search(r"[a-zA-Z]", l)]
    return "\n".join(lines[:150])


def _collect(soup, selectors, limit=60) -> str:
    seen, parts = set(), []
    for sel in selectors:
        for el in soup.select(sel):
            t = el.get_text(" ", strip=True)
            if t and len(t) > 3 and t not in seen:
                seen.add(t)
                parts.append(t)
                if len(parts) >= limit:
                    return "\n".join(parts)
    return "\n".join(parts)


# ============================================================================
#  Layer 3 — cert ID extraction + platform API
# ============================================================================

def _id_from_url(url: str, domain: str) -> str:

    # ── Udemy ─────────────────────────────────────────────────────────────────
    if "udemy" in domain or "ude.my" in domain:
        # Supports both formats:
        #   Short:    UC-ABCD1234
        #   UUID:     UC-0d3c6da7-7366-406c-8748-03c575ce58ab
        m = re.search(r"(UC-[a-zA-Z0-9][a-zA-Z0-9\-]*)", url, re.IGNORECASE)
        if not m:
            # fallback: grab everything after /certificate/
            m2 = re.search(r"certificate/([a-zA-Z0-9\-]+)", url)
            cert_id = m2.group(1).upper() if m2 else None
        else:
            cert_id = m.group(1).upper()

        if cert_id:
            if not cert_id.startswith("UC-"):
                cert_id = "UC-" + cert_id

            print(f"[udemy] extracted cert_id={cert_id}")

            # Try Udemy's public certificate metadata API
            try:
                session = _session()
                session.headers.update({"Accept": "application/json"})
                api_url = f"https://www.udemy.com/api-2.0/certificates/{cert_id}/"
                resp = session.get(api_url, timeout=15)
                print(f"[udemy_api] status={resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    parts = [f"Certificate ID: {cert_id}", "Issued by: Udemy"]
                    for key in ("user_name", "name", "display_name"):
                        if data.get(key):
                            parts.append(f"Student Name: {data[key]}")
                            break
                    for key in ("course_title", "title", "course_name"):
                        if data.get(key):
                            parts.append(f"Course: {data[key]}")
                            break
                    for key in ("completion_date", "create_date", "issued_date"):
                        if data.get(key):
                            parts.append(f"Completion Date: {data[key]}")
                            break
                    return "\n".join(parts)
            except Exception as e:
                print(f"[udemy_api] failed: {e}")

            # ID-only fallback — certificate_id field can still be matched
            return (
                f"Udemy Certificate\n"
                f"Certificate ID: {cert_id}\n"
                f"Issued by: Udemy\n"
                f"[Udemy blocked full access. Install Playwright for complete scraping:\n"
                f" pip install playwright && playwright install chromium]"
            )

    # ── Coursera ──────────────────────────────────────────────────────────────
    if "coursera" in domain:
        m = re.search(r"verify/([a-zA-Z0-9]+)", url)
        if m:
            return (
                f"Coursera Certificate\n"
                f"Certificate ID: {m.group(1)}\n"
                f"Issued by: Coursera\n"
                f"[Extracted from URL]"
            )

    return ""
