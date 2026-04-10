"""
utils/compare.py
────────────────
Strict field-comparison helper used by the NPTEL workflow.

Provides:
    _strict_compare(uploaded_ocr, official_text, u_fields, o_fields) -> dict
"""

from services.comparator import compare_certificates


def _strict_compare(
    uploaded_ocr: dict,
    official_text: str,
    u_fields: dict,
    o_fields: dict,
) -> dict:
    """
    Run strict comparison between uploaded OCR fields and official fields.

    Returns a standardised comparison dict with verification_status:
        "VALID"   — all fields matched
        "FAKE"    — one or more fields failed
        "UNKNOWN" — could not compare
        "OCR_FAILED"       — uploaded OCR produced no text
        "NO_OFFICIAL_TEXT" — official PDF returned no text
    """
    u_text = (uploaded_ocr.get("text") or "").strip()
    o_text = (official_text or "").strip()

    if not uploaded_ocr.get("success") or not u_text:
        return {
            "can_compare":         False,
            "score":               0.0,
            "field_comparison":    {},
            "verification_status": "OCR_FAILED",
            "reason":              "Uploaded certificate OCR produced no text. Install Tesseract.",
        }

    if not o_text:
        return {
            "can_compare":         False,
            "score":               0.0,
            "field_comparison":    {},
            "verification_status": "NO_OFFICIAL_TEXT",
            "reason":              "No text retrieved from official NPTEL certificate PDF.",
        }

    cmp     = compare_certificates(u_fields, o_fields, u_text, o_text)
    score   = cmp["score"]
    verdict = cmp.get("verdict", "UNVERIFIED")
    reason  = cmp.get("verdict_reason", "")

    status_map = {"GENUINE": "VALID", "FAKE": "FAKE", "UNVERIFIED": "UNKNOWN"}

    return {
        "can_compare":         True,
        "reason":              reason,
        "score":               score,
        "field_comparison":    cmp["field_matches"],
        "field_matches":       cmp["field_matches"],
        "failed_fields":       cmp.get("failed_fields", []),
        "not_found":           cmp.get("not_found", []),
        "verification_status": status_map.get(verdict, "UNKNOWN"),
    }
