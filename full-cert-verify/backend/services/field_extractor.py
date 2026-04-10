"""
Unified Field Extractor (IMPROVED)
Supports NPTEL + CodeTantra
"""

import re


def extract_fields(text: str, provider: str, pdf_url: str = "") -> dict:
    if not text:
        return {}

    text = _clean_text(text)

    if provider == "nptel":
        return _extract_nptel(text, pdf_url)

    elif provider == "codetantra":
        return _extract_codetantra(text)

    return {}


# ───────────────── COMMON CLEANING ─────────────────

def _clean_text(text: str) -> str:
    # remove weird unicode + normalize spaces
    text = re.sub(r'[\u200b\u200c\u200d\ufeff\u00ad\u2060]', '', text)
    text = re.sub(r'[\xa0\t\r]+', ' ', text)
    text = re.sub(r'\n+', '\n', text)
    return text.strip()


# ───────────────── NPTEL ─────────────────

def _extract_nptel(text: str, pdf_url: str = "") -> dict:
    fields = {}

    lines = [l.strip() for l in text.split('\n') if l.strip()]
    flat = re.sub(r'\s+', ' ', text)

    # ── Candidate Name (robust)
    for i, line in enumerate(lines):
        if "awarded to" in line.lower():
            val = _get_after_anchor(line, "awarded to")
            if val:
                fields["candidate_name"] = val
            elif i + 1 < len(lines):
                fields["candidate_name"] = lines[i + 1]
            break

    # ── Course Name
    for i, line in enumerate(lines):
        if "completing the course" in line.lower():
            val = _get_after_anchor(line, "completing the course")
            if val:
                fields["course_name"] = val
            elif i + 1 < len(lines):
                fields["course_name"] = lines[i + 1]
            break

    # ── Roll / Cert ID
    m = re.search(r"(NPTEL[A-Z0-9]{10,})", flat, re.I)
    if m:
        fields["roll_or_cert_id"] = m.group(1).upper()
    elif pdf_url:
        m2 = re.search(r"(NPTEL[A-Z0-9]{10,})", pdf_url, re.I)
        if m2:
            fields["roll_or_cert_id"] = m2.group(1).upper()

    # ── Duration
    m = re.search(r"(\d+\s*week(?:s)?(?:\s*course)?)", flat, re.I)
    if m:
        fields["course_duration"] = m.group(1).lower()

    # ── Date
    month = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
    pattern = rf"({month}\s*[-–—_]*\s*(?:{month})?\s*20\d{{2}})"
    m = re.search(pattern, flat, re.I)

    if m:
        raw = m.group(1)
        clean = re.sub(r'\s*[-–—_]+\s*', '-', raw)
        clean = re.sub(r'\s+', ' ', clean)
        fields["issue_date"] = clean.title()

    return fields


# ───────────────── CodeTantra ─────────────────

def _extract_codetantra(text: str) -> dict:
    fields = {}

    flat = re.sub(r'\s+', ' ', text)

    # ── Certificate ID
    m = re.search(r'(CT\d{4}-[A-Z0-9]+-[A-Z0-9]+)', flat, re.I)
    if m:
        fields["certificate_id"] = m.group(1).upper()

    # ── Name (more robust)
    name_patterns = [
        r'certify\s+that\s+([A-Za-z\s]+?)\s*\(',
        r'certify\s+that\s+([A-Za-z\s]+?)\s+has\b',
        r'certify\s+that\s+([A-Za-z\s]+?)\s+successfully',
        r'awarded\s+to\s+([A-Za-z\s]+?)\s*[(\n]',
    ]

    for p in name_patterns:
        m = re.search(p, text, re.I | re.S)
        if m:
            fields["name"] = _clean_value(m.group(1))
            break

    # ── Course (better patterns)
    course_patterns = [
        r'titled\s+(.*?)\s+from\b',
        r'course\s+titled\s+(.*?)\s+from\b',
        r'titled\s+(.*?)\s+conducted\b',
        r'course\s+on\s+(.*?)\s+(?:from|during|conducted)',
    ]

    for p in course_patterns:
        m = re.search(p, text, re.I | re.S)
        if m:
            fields["course"] = _clean_value(m.group(1))
            break

    # ── Date (cleaned)
    m = re.search(r'Date[:\s]+([A-Za-z0-9,\s/-]+)', flat, re.I)
    if m:
        fields["date"] = _clean_value(m.group(1))

    return fields


# ───────────────── HELPERS ─────────────────

def _get_after_anchor(line: str, anchor: str):
    parts = re.split(re.escape(anchor), line, flags=re.I)
    if len(parts) > 1:
        val = parts[1].strip()
        val = re.sub(r'^[:\-]\s*', '', val)
        if len(val) > 2:
            return val
    return None


def _clean_value(val: str) -> str:
    val = val.replace('\n', ' ')
    val = re.sub(r'\s+', ' ', val)
    return val.strip()