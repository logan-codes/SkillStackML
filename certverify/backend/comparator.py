"""
Comparator - NPTEL certificate field extractor & scorer.

Real NPTEL PDFs render decorative text as images — actual extractable text:
  MOHAMED MUZAMMIL M           ← Line 0: all-caps name
  70
  25/25
  45.25/75
  15570
  NPTEL24CS105S1233103512
  ...Jul-Oct 2024(12 week course)Programming in Java   ← footer

So extraction uses POSITIONAL logic, not anchor phrases.
"""

import re
import difflib

try:
    from rapidfuzz import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False


def extract_key_fields(text):
    if not text:
        return {}
    fields = {}
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # ── 1. Candidate Name ─────────────────────────────────────────────────────
    # Try anchor phrase first (some certs have readable text)
    for pat in [
        r"(?:This\s+certificate\s+is\s+awarded\s+to\s*\n\s*)([A-Z][A-Z\s\.]{2,50}?)(?:\s*\n)",
        r"(?:awarded\s+to\s*\n\s*)([A-Z][A-Z\s\.]{2,50}?)(?:\s*\n)",
        r"(?:certif(?:y|ied)\s+that\s+)([\w\s\.]{3,50}?)(?:\s+has|\n)",
    ]:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            fields["candidate_name"] = re.sub(r"\s+", " ", m.group(1).strip())
            break

    # Positional fallback: first standalone all-caps line
    if "candidate_name" not in fields:
        for line in lines:
            if (re.match(r'^[A-Z][A-Z\s\.]{4,50}$', line)
                    and not line.startswith("NPTEL")
                    and not re.search(r'\d{4}', line)):
                fields["candidate_name"] = line
                break

    # ── 2. Course Name ────────────────────────────────────────────────────────
    # Try anchor phrase first
    for pat in [
        r"(?:for\s+successfully\s+completing\s+the\s+course\s*\n\s*)([^\n]+)",
        r"(?:completing\s+the\s+course\s*\n\s*)([^\n]+)",
        r"(?:course\s+on\s+)([\w\s,\-&:\/]+?)(?:\s+conducted|\n|$)",
    ]:
        m = re.search(pat, text, re.IGNORECASE | re.MULTILINE)
        if m:
            fields["course_name"] = re.sub(r"\s+", " ", m.group(1).strip())
            break

    # Positional fallback: text immediately after "(N week course)"
    if "course_name" not in fields:
        m = re.search(r'\(\d+\s*week\s*course\)\s*([\w][\w\s,\-&:]+?)(?:\s*$|\n)',
                      text, re.IGNORECASE | re.MULTILINE)
        if m:
            fields["course_name"] = re.sub(r"\s+", " ", m.group(1).strip())

    # ── 3. Course Duration — extract weeks from "(12 week course)" ───────────
    for pat in [
        r"\((\d+\s*week(?:s)?\s*course)\)",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            fields["course_duration"] = re.sub(r"\s+", " ", m.group(1).strip())
            break

    # ── 4. Roll No / Certificate ID ───────────────────────────────────────────
    for pat in [
        r"Roll\s+No[:\s]+\s*(NPTEL[\w]+)",
        r"\b(NPTEL\d{2}[A-Z]{2}\d+[A-Z]\d+)\b",
        r"Roll\s+No[:\s]+([\w\-]{6,})",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            fields["roll_or_cert_id"] = re.sub(r"\s+", " ", m.group(1).strip())
            break

    # ── 5. Issue Date = session (Jan-Apr / Jul-Oct YYYY) ─────────────────────
    for pat in [
        r"\b(Jan(?:uary)?[\-\u2013]Apr(?:il)?\s*20\d{2})\b",
        r"\b(Jul(?:y)?[\-\u2013]Oct(?:ober)?\s*20\d{2})\b",
        r"\b((?:Jan|Jul)-(?:Apr|Oct)\s+20\d{2})\b",
        r"(?:date\s+of\s+issue\s*[:\-]\s*)([\w\s,\/\-]+?\d{4})",
        r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})\b",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            fields["issue_date"] = re.sub(r"\s+", " ", m.group(1).strip())
            break

    return fields


# ── Normalization & similarity ─────────────────────────────────────────────────

def _normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _similarity(a, b):
    if not a or not b:
        return 0.0
    a, b = _normalize(a), _normalize(b)
    if FUZZY_AVAILABLE:
        return fuzz.token_sort_ratio(a, b) / 100.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ── Scoring ────────────────────────────────────────────────────────────────────

def compare_certificates(uploaded_fields, official_fields, uploaded_text, official_text):
    WEIGHTS = {
        "candidate_name":  0.30,
        "course_name":     0.25,
        "roll_or_cert_id": 0.20,
        "course_duration": 0.15,
        "issue_date":      0.10,
    }
    LABELS = {
        "candidate_name":  "Candidate Name",
        "course_name":     "Course Name",
        "roll_or_cert_id": "Roll No / Certificate ID",
        "course_duration": "Course Duration",
        "issue_date":      "Date",
    }

    field_matches  = {}
    weighted_score = 0.0

    for field, weight in WEIGHTS.items():
        uval = uploaded_fields.get(field, "").strip()
        oval = official_fields.get(field, "").strip()

        if uval and oval:
            sim = _similarity(uval, oval)
            # All fields must match exactly (case-insensitive, punctuation-normalized)
            matched = _normalize(uval) == _normalize(oval)
            field_matches[field] = {
                "label":      LABELS[field],
                "uploaded":   uval,
                "official":   oval,
                "similarity": round(sim, 3),
                "match":      matched,
                "weight":     weight,
            }
            weighted_score += sim * weight
        elif uval or oval:
            field_matches[field] = {
                "label":      LABELS[field],
                "uploaded":   uval,
                "official":   oval,
                "similarity": 0.0,
                "match":      False,
                "weight":     weight,
            }
        else:
            field_matches[field] = {
                "label":      LABELS[field],
                "uploaded":   "",
                "official":   "",
                "similarity": None,
                "match":      None,
                "weight":     weight,
            }

    # ── Strict verdict: ALL 5 fields must match, any failure = FAKE ─────────
    failed_fields = [
        v["label"] for v in field_matches.values()
        if v["match"] is False   # compared but didn't match
    ]
    not_found = [
        v["label"] for v in field_matches.values()
        if v["match"] is None    # could not extract from OCR
    ]

    # Any mismatch OR any unextractable field = FAKE
    if failed_fields or not_found:
        all_bad = failed_fields + not_found
        verdict = "FAKE"
        verdict_reason = f"Failed fields: {', '.join(all_bad)}"
    else:
        verdict = "GENUINE"
        verdict_reason = "All 5 fields match the official NPTEL record."

    return {
        "score":          round(weighted_score, 4),
        "fields_found":   sum(1 for v in field_matches.values() if v["match"] is True),
        "field_matches":  field_matches,
        "verdict":        verdict,
        "verdict_reason": verdict_reason,
        "failed_fields":  failed_fields,
        "not_found":      not_found,
    }
