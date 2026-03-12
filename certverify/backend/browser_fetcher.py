"""
Browser Fetcher — uses Playwright headless Chromium to:
  1. Visit the certificate URL like a real browser
  2. Wait for the page to fully render (handles JS-heavy pages)
  3. Take a full-page screenshot
  4. Run OCR on that screenshot
  5. Also extract visible text from the DOM

This bypasses most bot-detection since it's a real browser engine.
"""

import os
import tempfile
import time

# Check if playwright is available
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from ocr_engine import extract_text


def is_available():
    return PLAYWRIGHT_AVAILABLE


def fetch_with_browser(url: str) -> dict:
    """
    Launch headless Chromium, visit the URL, screenshot it, and OCR it.

    Returns dict:
      {
        "text":        str,   # combined DOM text + OCR text
        "dom_text":    str,   # text extracted directly from DOM
        "ocr_text":    str,   # text from OCR on screenshot
        "screenshot":  bytes, # PNG screenshot bytes (for debugging)
        "method":      str,   # "browser_screenshot"
      }
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright is not installed.\n"
            "Run these two commands:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    print(f"[browser_fetcher] launching Chromium for: {url}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            # Hide that we're automated
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        # Mask automation signals
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        """)

        page = context.new_page()

        try:
            print(f"[browser_fetcher] navigating...")
            page.goto(url, wait_until="networkidle", timeout=30000)

            # Extra wait for JS-rendered content
            page.wait_for_timeout(3000)

            # Scroll down to trigger lazy-load
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(500)

            print(f"[browser_fetcher] page loaded — taking screenshot")

            # Full-page screenshot
            screenshot_bytes = page.screenshot(full_page=True, type="png")
            print(f"[browser_fetcher] screenshot size = {len(screenshot_bytes)} bytes")

            # Extract DOM text
            dom_text = _extract_dom_text(page)
            print(f"[browser_fetcher] DOM text = {len(dom_text)} chars")

            # OCR the screenshot
            ocr_text = _ocr_screenshot(screenshot_bytes)
            print(f"[browser_fetcher] OCR text = {len(ocr_text)} chars")

            # Combine — DOM text is usually cleaner, OCR catches graphics/canvas text
            combined = _merge_texts(dom_text, ocr_text)

            return {
                "text":       combined,
                "dom_text":   dom_text,
                "ocr_text":   ocr_text,
                "screenshot": screenshot_bytes,
                "method":     "browser_screenshot",
            }

        except PWTimeout:
            raise RuntimeError(
                f"Page load timed out after 30 seconds.\n"
                f"The site may be slow or blocking headless browsers."
            )
        except Exception as e:
            raise RuntimeError(f"Browser fetch failed: {e}")
        finally:
            context.close()
            browser.close()


def _extract_dom_text(page) -> str:
    """Extract all visible text from the rendered DOM."""
    try:
        # Remove noise elements first
        page.evaluate("""
            ['script','style','nav','footer','header','noscript','iframe'].forEach(tag => {
                document.querySelectorAll(tag).forEach(el => el.remove());
            });
        """)

        # Get innerText of body (respects visibility, line breaks, etc.)
        text = page.evaluate("document.body ? document.body.innerText : ''")
        if text:
            lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 3]
            return "\n".join(lines[:200])
    except Exception as e:
        print(f"[browser_fetcher] DOM extract error: {e}")
    return ""


def _ocr_screenshot(png_bytes: bytes) -> str:
    """Save screenshot to temp file and run OCR."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(png_bytes)
            tmp_path = tmp.name
        return extract_text(tmp_path).get("text", "")
    except Exception as e:
        print(f"[browser_fetcher] OCR error: {e}")
        return ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _merge_texts(dom_text: str, ocr_text: str) -> str:
    """Combine DOM and OCR texts, deduplicating overlapping lines."""
    if not ocr_text:
        return dom_text
    if not dom_text:
        return ocr_text

    # Use DOM text as primary (cleaner), append unique OCR lines
    dom_lines = set(l.strip().lower() for l in dom_text.splitlines() if l.strip())
    extra = []
    for line in ocr_text.splitlines():
        ls = line.strip()
        if ls and ls.lower() not in dom_lines and len(ls) > 5:
            extra.append(ls)

    if extra:
        return dom_text + "\n\n[OCR from screenshot]\n" + "\n".join(extra)
    return dom_text
