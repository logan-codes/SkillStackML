"""
workflows/coursera.py
─────────────────────
Coursera Certificate Verification Workflow.

Pipeline:
    1. Convert uploaded PDF/image → JPEG
    2. Groq Vision AI extracts: name, course, date, certificate_id, verify_url
    3. Clean cert_id (alphanumeric only), detect professional-cert vs regular
    4. Download official S3 image (3 retries)
       → blocked: return status="retry"
    5. Vision AI reads official image
    6. Ping verify URL (HTTP 200 check)
    7. AI semantic comparison: name, course, date
    8. ALL checks pass → GENUINE, any failure → FAKE
"""

import re
import requests
import time

from schema.workflow      import Workflow
from services.groq_client import extract_with_vision, ai_compare
from utils.file_utils     import to_image_bytes, normalize_date, normalize
from core.logger          import get_logger

logger = get_logger(__name__)

# ── Groq Vision prompt for Coursera ──────────────────────────
VISION_PROMPT = """This is a Coursera certificate image. Extract and return JSON only with these exact keys:

{
  "name": "recipient full name e.g. PRAKHAR KUMAR",
  "course": "course or specialization title only e.g. Google Cybersecurity or Google AI Essentials",
  "date": "completion date cleaned e.g. Aug 22, 2024",
  "certificate_id": "alphanumeric cert ID only e.g. L88WVCA0EYB9 or YA89YSLKMQSA",
  "verify_url": "full reconstructed verify URL e.g. https://coursera.org/verify/professional-cert/L88WVCA0EYB9"
}

Important rules:
- The verify URL may be split across two lines — join them into one complete URL
- If URL contains "professional-cert" reconstruct as https://coursera.org/verify/professional-cert/{ID}
- Otherwise reconstruct as https://coursera.org/verify/{ID}
- certificate_id is ONLY the alphanumeric ID at the end of the verify URL
- course is ONLY the title, not phrases like "has successfully completed"
- date should have no extra spaces

Return ONLY valid JSON, nothing else."""

IMG_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.coursera.org/",
}


class CourseraWorkflow(Workflow):
    """Verification workflow for Coursera certificates."""

    def __init__(self):
        super().__init__(
            provider   = "coursera",
            name       = "Coursera Workflow",
            req_fields = ["contents", "content_type"],
        )

    # ── Official image download ──────────────────────────────

    def _download_official_image(self, cert_id: str) -> tuple:
        """
        Download the official Coursera certificate image from S3.
        Pattern: s3.amazonaws.com/coursera_assets/meta_images/generated/
                 CERTIFICATE_LANDING_PAGE/CERTIFICATE_LANDING_PAGE~{id}/
                 CERTIFICATE_LANDING_PAGE~{id}.jpeg

        Returns (image_bytes, image_url) or (None, url) on failure.
        """
        url = (
            f"https://s3.amazonaws.com/coursera_assets/meta_images/generated/"
            f"CERTIFICATE_LANDING_PAGE/CERTIFICATE_LANDING_PAGE~{cert_id}/"
            f"CERTIFICATE_LANDING_PAGE~{cert_id}.jpeg"
        )
        logger.info(f"[Official] Downloading: {url}")

        for attempt in range(1, 4):
            try:
                resp = requests.get(url, headers=IMG_HEADERS, timeout=20)
                logger.info(f"[Official] Attempt {attempt}: HTTP {resp.status_code}")
                if resp.status_code == 200 and "image" in resp.headers.get("content-type", ""):
                    return resp.content, url
                time.sleep(3 * attempt)
            except Exception as e:
                logger.error(f"[Official] Error on attempt {attempt}: {e}")
                time.sleep(3 * attempt)

        return None, url

    # ── Process ─────────────────────────────────────────────

    def process(self, payload: dict) -> dict:
        """
        Verify a Coursera certificate.

        Required payload keys:
            contents     (bytes) — raw file bytes
            content_type (str)   — MIME type

        Returns:
            Standard response dict.
        """
        contents     = payload["contents"]
        content_type = payload["content_type"]

        logger.info("Coursera workflow started")

        # ── Step 1: Convert to JPEG + Vision AI ─────────────
        logger.info("Step 1 — Convert PDF/image to JPEG")
        image_bytes = to_image_bytes(contents, content_type)

        logger.info("Step 2 — Vision AI extraction on uploaded cert")
        uploaded = extract_with_vision(image_bytes, VISION_PROMPT, label="UPLOADED")
        for k in ["name", "course", "date", "certificate_id", "verify_url"]:
            if k not in uploaded:
                uploaded[k] = None

        # ── Clean cert_id (alphanumeric only) ────────────────
        cert_id = re.sub(r'[^A-Z0-9]', '', (uploaded.get("certificate_id") or "").upper())
        uploaded["certificate_id"] = cert_id
        logger.info(f"cert_id={cert_id}")

        # ── Detect professional cert ─────────────────────────
        raw_url    = str(uploaded.get("verify_url") or "").lower()
        raw_course = str(uploaded.get("course") or "").lower()
        is_professional = (
            "professional-cert" in raw_url
            or "professional certificate" in raw_course
            or "specialization" in raw_course
        )
        verify_url = (
            f"https://coursera.org/verify/professional-cert/{cert_id}"
            if is_professional
            else f"https://coursera.org/verify/{cert_id}"
        ) if cert_id else raw_url
        uploaded["verify_url"] = verify_url

        # ── Step 3: Download official image ─────────────────
        logger.info("Step 3 — Download official Coursera S3 image")
        official_bytes, image_url = self._download_official_image(cert_id)

        if not official_bytes:
            logger.warning("Official image unavailable — returning retry")
            return {
                "status":       "retry",
                "message":      "Official certificate image could not be fetched. Please try again.",
                "certificate_id": cert_id,
                "verify_url":   verify_url,
                "uploaded_data": uploaded,
            }

        # ── Step 4: Vision AI on official image ─────────────
        logger.info("Step 4 — Vision AI on official image")
        official = extract_with_vision(official_bytes, VISION_PROMPT, label="OFFICIAL")
        for k in ["name", "course", "date", "certificate_id", "verify_url"]:
            if k not in official:
                official[k] = None

        # ── Step 5: Ping verify URL ──────────────────────────
        logger.info("Step 5 — Verify URL ping")
        try:
            vresp = requests.get(
                verify_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
                allow_redirects=True,
            )
            verify_valid = vresp.status_code == 200
        except Exception:
            verify_valid = False
        logger.info(f"URL ping: {'OK' if verify_valid else 'FAILED'}")

        # ── Step 6: AI semantic comparison ───────────────────
        logger.info("Step 6 — AI semantic comparison")

        def strict_compare(a, b, field):
            """
            Strict comparison:
            - Exact normalize match → True immediately
            - One is substring of other → False (catches Vision AI truncation)
            - Only call AI for genuinely different words
            """
            if not a or not b:
                return False
            na = normalize(a)
            nb = normalize(b)
            if na == nb:
                logger.info(f"[{field}] exact match ✓")
                return True
            if na in nb or nb in na:
                logger.info(f"[{field}] substring mismatch ✗ — '{na}' vs '{nb}'")
                return False
            return ai_compare(a, b, field)

        name_match   = strict_compare(uploaded.get("name"),   official.get("name"),   "name")
        course_match = strict_compare(uploaded.get("course"), official.get("course"), "course")
        date_match   = normalize_date(uploaded.get("date")) == normalize_date(official.get("date"))

        is_genuine = verify_valid and name_match and course_match and date_match
        score = sum([name_match, course_match, date_match, verify_valid]) * 25
        logger.info(f"Verdict: {'GENUINE' if is_genuine else 'FAKE'}  score={score}%")

        return {
            "status":        "success",
            "is_genuine":    is_genuine,
            "overall_score": f"{score}%",
            "message":       "Valid Certificate" if is_genuine else "Tampered / Fake Certificate Detected",
            "verify_url":    verify_url,
            "official_image": image_url,
            "field_breakdown": {
                "url_valid": {"result": verify_valid},
                "name":      {"uploaded": uploaded.get("name"),   "official": official.get("name"),   "result": name_match},
                "course":    {"uploaded": uploaded.get("course"), "official": official.get("course"), "result": course_match},
                "date":      {"uploaded": uploaded.get("date"),   "official": official.get("date"),   "result": date_match,
                              "normalized_uploaded": normalize_date(uploaded.get("date")),
                              "normalized_official": normalize_date(official.get("date"))},
            },
            "data": {"uploaded_data": uploaded, "official_data": official},
        }


# ── Module-level exports ─────────────────────────────────────
_instance = CourseraWorkflow()
METADATA  = _instance.METADATA
validate  = _instance.validate
process   = _instance.process