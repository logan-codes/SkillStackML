import io
import re
import time
import asyncio
import datetime
import requests
from bs4 import BeautifulSoup
from PIL import Image
import pytesseract
import fitz  # PyMuPDF
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Simplilearn Certificate Verification API", version="9.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/jpg"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.simplilearn.com/",
}

MONTHS = {
    "january":1,"february":2,"march":3,"april":4,"may":5,"june":6,
    "july":7,"august":8,"september":9,"october":10,"november":11,"december":12
}

# ============================================================
#  HELPERS
# ============================================================

def normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', str(text)).strip().lower()

def normalize_date(text: str) -> str:
    """Convert any date format to YYYY-MM-DD for comparison."""
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r'(\d+)(st|nd|rd|th)', r'\1', text)

    m = re.search(
        r'(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})',
        text
    )
    if m:
        day, month, year = int(m.group(1)), MONTHS[m.group(2)], int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    m = re.search(
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})',
        text
    )
    if m:
        month, day, year = MONTHS[m.group(1)], int(m.group(2)), int(m.group(3))
        return f"{year:04d}-{month:02d}-{day:02d}"

    m = re.search(r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})', text)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"

    return normalize(text)

def date_from_image_url(url: str) -> str | None:
    match = re.search(r'_(\d{13})\.png', url)
    if match:
        ts_ms = int(match.group(1))
        dt = datetime.datetime.fromtimestamp(ts_ms / 1000, tz=datetime.timezone.utc)
        return dt.strftime("%B %d, %Y")
    return None

# ============================================================
#  STEP 1 — OCR uploaded file
# ============================================================

def ocr_uploaded_file(contents: bytes, content_type: str) -> dict:
    extracted = ""
    if content_type == "application/pdf":
        pdf_doc = fitz.open(stream=contents, filetype="pdf")
        for page_num in range(len(pdf_doc)):
            page = pdf_doc.load_page(page_num)
            page_text = page.get_text()
            if len(page_text.strip()) < 15:
                pix = page.get_pixmap(dpi=300)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                page_text = pytesseract.image_to_string(img)
            extracted += page_text + "\n"
    elif content_type in ["image/jpeg", "image/png", "image/jpg"]:
        image = Image.open(io.BytesIO(contents))
        w, h = image.size
        image = image.resize((w * 2, h * 2), Image.LANCZOS)
        extracted = pytesseract.image_to_string(image)

    text = extracted.strip()
    print(f"[Uploaded OCR]\n{text}\n---")

    result = {"name": None, "course": None, "date": None, "certificate_code": None}

    # Name
    for line in text.splitlines():
        line = line.strip()
        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]*){1,3}$', line):
            result["name"] = line
            break

    # Course
    for line in text.splitlines():
        line = line.strip()
        if re.search(r'(Python|Java|Web|Data|ML|AI|Cloud|Cyber|Digital|SQL|Excel|Power|Machine|Deep|Analytics|Beginner|Advanced|RAG|Application|Developer|Programming|Security|Network)', line, re.IGNORECASE):
            if 3 < len(line) < 100:
                result["course"] = line
                break

    # Date
    date_match = re.search(
        r'(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|'
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}|'
        r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})',
        text, re.IGNORECASE
    )
    if date_match:
        result["date"] = date_match.group(0).strip()

    # Certificate Code
    code_match = re.search(r'(?:certificate\s*code\s*[:\-]?\s*)(\d+)', text, re.IGNORECASE)
    if code_match:
        result["certificate_code"] = code_match.group(1)

    print(f"[Uploaded Fields] {result}")
    return result

# ============================================================
#  STEP 2 — Scrape official page
# ============================================================

def scrape_official_page(cert_url: str) -> dict:
    result = {"name": None, "course": None, "date": None, "certificate_code": None, "url_valid": False}
    timeouts = [10, 20, 30]

    for attempt in range(1, 4):
        try:
            print(f"[Scraper] Attempt {attempt}/3 — {cert_url}")
            resp = requests.get(cert_url, headers=HEADERS, timeout=timeouts[attempt - 1])

            if resp.status_code == 200:
                result["url_valid"] = True
                soup = BeautifulSoup(resp.text, 'html.parser')
                full_text = soup.get_text(separator=' ', strip=True)
                print(f"[Scraper] Full text:\n{full_text[:500]}\n---")

                # Name — try all sources
                for meta in soup.find_all('meta'):
                    content = meta.get('content', '')
                    nm = re.match(r'^([A-Za-z][A-Za-z\s\.]+?)\s+has successfully', content, re.IGNORECASE)
                    if nm:
                        result["name"] = nm.group(1).strip()
                        break

                if not result["name"]:
                    nm = re.search(r'verifies that\s+([A-Za-z][A-Za-z\s\.]+?)\s+has successfully', full_text, re.IGNORECASE)
                    if nm:
                        result["name"] = nm.group(1).strip()

                if not result["name"]:
                    nm = re.search(r'Course completed by\s+([A-Za-z][A-Za-z\s\.]+?)(?:\s{2,}|$)', full_text, re.IGNORECASE)
                    if nm:
                        result["name"] = nm.group(1).strip()

                # Course — from <strong> tag
                strong = soup.find('strong')
                if strong:
                    result["course"] = strong.get_text(strip=True)
                else:
                    cm = re.search(r'completed the course\s*([A-Za-z0-9][^\n]{3,80}?)(?:\s{2,}|Learn|$)', full_text, re.IGNORECASE)
                    if cm:
                        result["course"] = cm.group(1).strip()

                # Date from image URL timestamp
                for img in soup.find_all('img'):
                    src = img.get('src', '')
                    if 'simplicdn.net/share' in src:
                        result["date"] = date_from_image_url(src)
                        # Extract certificate code from image URL (first number)
                        code_match = re.search(r'share/(\d+)_', src)
                        if code_match:
                            result["certificate_code"] = code_match.group(1)
                        print(f"[Scraper] Date: {result['date']} | Cert Code: {result['certificate_code']}")
                        break

                print(f"[Scraper] Official -> {result}")
                return result

            else:
                print(f"[Scraper] HTTP {resp.status_code}")
                result["url_valid"] = False
                return result

        except requests.Timeout:
            print(f"[Scraper] Timeout on attempt {attempt}")
        except Exception as e:
            print(f"[Scraper] Error: {e}")

        if attempt < 3:
            time.sleep(2)

    return result

# ============================================================
#  API
# ============================================================

@app.get("/")
def root():
    return {"message": "Simplilearn Certificate Verification API v9.0 running."}


@app.post("/verify-certificate/")
async def verify_certificate(
    file: UploadFile = File(...),
    cert_url: str = Form(...),
):
    if file.content_type not in SUPPORTED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type. Accepted: PDF, JPG, PNG.")
    if not cert_url.strip():
        raise HTTPException(status_code=400, detail="cert_url is required.")

    try:
        contents = await file.read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {e}")

    # Step 1 — OCR uploaded file
    uploaded = await asyncio.to_thread(ocr_uploaded_file, contents, file.content_type)

    # Step 2 — Scrape official page
    official = await asyncio.to_thread(scrape_official_page, cert_url.strip())

    print(f"[Process] Uploaded -> {uploaded}")
    print(f"[Process] Official -> {official}")

    # Step 3 — URL / Cert code verification
    url_valid      = official.get("url_valid", False)
    uploaded_code  = uploaded.get("certificate_code")
    official_code  = official.get("certificate_code")
    code_match     = (uploaded_code == official_code) if (uploaded_code and official_code) else None

    # Step 4 — Exact field comparison
    name_match   = normalize(uploaded.get("name"))   == normalize(official.get("name"))
    name_score   = 100.0 if name_match else 0.0
    course_match = normalize(uploaded.get("course")) == normalize(official.get("course"))
    course_score = 100.0 if course_match else 0.0

    # Date — normalize then exact compare
    uploaded_date_norm = normalize_date(uploaded.get("date"))
    official_date_norm = normalize_date(official.get("date"))
    date_match         = uploaded_date_norm == official_date_norm
    date_score         = 100.0 if date_match else 0.0

    field_breakdown = {
        "url_valid": {
            "result": url_valid,
            "detail": "Certificate URL exists on Simplilearn" if url_valid else "Certificate URL not found"
        },
        "certificate_code": {
            "uploaded": uploaded_code,
            "official": official_code,
            "result":   code_match,
            "detail":   "Codes match" if code_match else ("No code found in uploaded file" if not uploaded_code else "Code mismatch")
        },
        "name": {
            "uploaded": uploaded.get("name"),
            "official": official.get("name"),
            "result":   name_match,
            "detail":   "Name matches" if name_match else "Name mismatch"
        },
        "course": {
            "uploaded": uploaded.get("course"),
            "official": official.get("course"),
            "result":   course_match,
            "detail":   "Course matches" if course_match else "Course mismatch"
        },
        "date": {
            "uploaded": uploaded.get("date"),
            "official": official.get("date"),
            "normalized_uploaded": uploaded_date_norm,
            "normalized_official": official_date_norm,
            "result":   date_match,
            "detail":   "Date matches" if date_match else "Date mismatch"
        },
    }

    # Verdict — URL must be valid + at least 3/4 other checks pass
    checks = [name_match, course_match, date_match, code_match if code_match is not None else True]
    is_genuine = url_valid and all(checks)

    # Overall score — only include fields that have data on both sides
    scores = [name_score, course_score, date_score]
    if code_match is not None:
        scores.append(100.0 if code_match else 0.0)
    overall_score = round(sum(scores) / len(scores), 1)

    print(f"[Process] Verdict -> {'GENUINE' if is_genuine else 'FAKE'} | Score: {overall_score}%")

    return {
        "status":        "Success",
        "is_genuine":    is_genuine,
        "overall_score": f"{overall_score}%",
        "message":       "✅ Valid Certificate" if is_genuine else "❌ Tampered / Fake Certificate Detected",
        "field_breakdown": field_breakdown,
    }
