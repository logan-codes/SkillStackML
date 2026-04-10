"""
Comparator - NPTEL certificate field extractor & scorer.

Pipeline Strategy:
1. Hybrid Extraction: Uses text anchors for uploaded OCR images, 
   and positional regex fallbacks for digitally native PDFs.
2. Normalization: Cleans punctuation and casing before comparison.
3. Strict Comparison: All 5 extracted fields MUST match to pass as GENUINE.
"""

import re
import difflib

try:
    from rapidfuzz import fuzz
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False


def extract_key_fields(text: str, pdf_url: str = "") -> dict:
    """
    Extracts the 5 key NPTEL fields using a hybrid approach:
    Anchors first (for OCR images), Positional fallbacks second (for native PDFs).
    """
    if not text:
        return {}
    
    fields = {}
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    flat_text = re.sub(r'\s+', ' ', text)

    # ── 1. Candidate Name ──
    # Strategy A: Anchors (For full OCR text)
    for i, line in enumerate(lines):
        lower_line = line.lower()
        if "awarded to" in lower_line and "candidate_name" not in fields:
            parts = re.split(re.escape("awarded to"), line, flags=re.IGNORECASE)
            if len(parts) > 1:
                rem = re.sub(r'^[:\-]\s*', '', parts[1].strip())
                if len(rem) > 2:
                    fields["candidate_name"] = rem
            elif i + 1 < len(lines):
                fields["candidate_name"] = lines[i + 1].strip()

    # Strategy B: Positional Fallback (For native PDFs missing the anchor)
    if "candidate_name" not in fields:
        for line in lines:
            # First all-caps line (2 to 50 chars) that isn't the NPTEL ID or a date
            if re.match(r'^[A-Z][A-Z\s\.]{1,50}$', line) and not line.startswith("NPTEL") and not re.search(r'\d', line):
                fields["candidate_name"] = line
                break


    # ── 2. Course Name ──
    # Strategy A: Anchors (For full OCR text)
    for i, line in enumerate(lines):
        lower_line = line.lower()
        if "completing the course" in lower_line and "course_name" not in fields:
            parts = re.split(re.escape("completing the course"), line, flags=re.IGNORECASE)
            if len(parts) > 1:
                rem = re.sub(r'^[:\-]\s*', '', parts[1].strip())
                if len(rem) > 2:
                    fields["course_name"] = rem
            elif i + 1 < len(lines):
                fields["course_name"] = lines[i + 1].strip()

    # Strategy B: Positional Fallback (For native PDFs)
    # In native PDFs, the course name is usually jammed right after the duration e.g., "(12 week course)Programming in Java"
    if "course_name" not in fields:
        m = re.search(r'\(\d+\s*week(?:s)?(?:\s*course)?\)\s*([a-zA-Z][\w\s,\-&:]+?)(?:\s*$|\n)', text, re.IGNORECASE)
        if m:
            fields["course_name"] = m.group(1).strip()


    # ── 3. Standalone Global Data ──
    # Roll Number
    m_roll = re.search(r"(NPTEL[A-Z0-9]{10,})", flat_text, re.IGNORECASE)
    if m_roll:
        fields["roll_or_cert_id"] = m_roll.group(1).upper()
    elif pdf_url:
        m_url = re.search(r"(NPTEL[A-Z0-9]{10,})", pdf_url, re.IGNORECASE)
        if m_url:
            fields["roll_or_cert_id"] = m_url.group(1).upper()

    # Course Duration
    m_duration = re.search(r"(\d+\s*week(?:s)?(?:\s*course)?)", flat_text, re.IGNORECASE)
    if m_duration:
        fields["course_duration"] = m_duration.group(1).lower()

    # Issue Date / Session Timeline
    month_regex = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
    date_pattern = rf"({month_regex}\s*[-–—_]*\s*(?:{month_regex})?\s*20\d{{2}})"
    m_date = re.search(date_pattern, flat_text, re.IGNORECASE)
    if m_date:
        raw_date = m_date.group(1)
        clean_date = re.sub(r'\s*[-–—_]+\s*', '-', raw_date)
        clean_date = re.sub(r'\s+', ' ', clean_date)
        fields["issue_date"] = clean_date.title()

    return fields


# ── Normalization & similarity ─────────────────────────────────────────────────

def _normalize(text):
    if not text:
        return ""
    text = text.lower()
    # Replace punctuation with spaces
    text = re.sub(r"[^\w\s]", " ", text)
    # Collapse multiple spaces into one
    return re.sub(r"\s+", " ", text).strip()


def _similarity(a, b):
    if not a or not b:
        return 0.0
    a, b = _normalize(a), _normalize(b)
    if FUZZY_AVAILABLE:
        return fuzz.token_sort_ratio(a, b) / 100.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# ── Scoring ────────────────────────────────────────────────────────────────────

def compare_certificates(uploaded_fields, official_fields, uploaded_text="", official_text=""):
    """
    Compares the 5 extracted fields. All must match for the certificate to be GENUINE.
    """
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
            # You can change this to sim > 0.85 if you want to allow minor OCR typos in the final verdict
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
        if v["match"] is None    # could not extract from either side
    ]

    # Any mismatch OR any unextractable field = FAKE
    if failed_fields or not_found:
        all_bad = failed_fields + not_found
        verdict = "FAKE"
        verdict_reason = f"Verification failed on: {', '.join(all_bad)}"
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