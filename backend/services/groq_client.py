"""
services/groq_client.py
───────────────────────
Shared Groq AI client used by Coursera and Udemy workflows.

Provides:
    extract_with_vision(image_bytes, prompt, label) -> dict
    ai_compare(val1, val2, field)                   -> bool
"""

import base64
import json
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

# ── Lazy-init Groq client ────────────────────────────────────
_client = None

def _get_client():
    global _client
    if _client is None:
        from groq import Groq
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


# ── Vision extraction ────────────────────────────────────────
def extract_with_vision(image_bytes: bytes, prompt: str, label: str = "") -> dict:
    """
    Send a JPEG image to Groq Vision AI (Llama 4 Scout) and parse the JSON response.

    Args:
        image_bytes: Raw JPEG bytes of the certificate image.
        prompt:      Extraction prompt that instructs the model to return JSON.
        label:       Log label e.g. "UPLOADED" or "OFFICIAL".

    Returns:
        Parsed dict from the model's JSON response.
        Falls back to all-None dict on parse error.
    """
    client = _get_client()
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model=settings.VISION_MODEL,
        max_tokens=400,
        response_format={"type": "json_object"},
        messages=[{
            "role": "user",
            "content": [
                {"type": "text",      "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
    )

    raw = response.choices[0].message.content.strip()
    logger.info(f"[Vision — {label}]: {raw[:200]}")

    try:
        return json.loads(raw)
    except Exception as e:
        logger.error(f"Vision JSON parse error: {e}")
        return {}


# ── Semantic comparison ──────────────────────────────────────
def ai_compare(val1: str, val2: str, field: str) -> bool:
    """
    Semantically compare two field values using Groq LLM.

    Fast path: exact match after normalization → returns True immediately.
    Slow path: LLM decides YES / NO for abbreviations, formatting differences, etc.

    Args:
        val1:  Value from uploaded certificate.
        val2:  Value from official source.
        field: Field name used in the prompt e.g. "name", "course".

    Returns:
        True if the values refer to the same thing, False otherwise.
    """
    if not val1 or not val2:
        return False

    # Fast path
    import re
    def _norm(t): return re.sub(r'\s+', ' ', str(t)).strip().lower()
    if _norm(val1) == _norm(val2):
        return True

    # LLM path
    client = _get_client()
    prompt = (
        f'Do these two "{field}" values refer to the same thing?\n'
        f"Value 1: {val1}\n"
        f"Value 2: {val2}\n"
        f"Consider abbreviations, & vs and, minor formatting differences.\n"
        f"Reply with only YES or NO."
    )
    resp = client.chat.completions.create(
        model=settings.COMPARE_MODEL,
        max_tokens=5,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = resp.choices[0].message.content.strip().upper()
    logger.info(f"[AI Compare — {field}]: '{val1[:30]}' vs '{val2[:30]}' → {answer}")
    return answer == "YES"
