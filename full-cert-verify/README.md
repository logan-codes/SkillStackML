# CertVerify — Multi-Platform Certificate Verification

Unified certificate verification system supporting **NPTEL**, **CodeTantra**, **Coursera**, and **Udemy** — powered by OCR, web scraping, and Groq Vision AI.

---

## Quick Start

```
Double-click  start.bat
```

That's it. The script will:
1. Create a Python virtual environment
2. Install all dependencies
3. Open the frontend in your browser
4. Start the backend API on `http://localhost:8000`

---

## Project Structure

```
certverify/
├── start.bat                    ← Single-command launcher (Windows)
│
├── backend/
│   ├── main.py                  ← FastAPI app entry point
│   ├── requirements.txt         ← All Python dependencies
│   ├── .env                     ← Environment config (add GROQ_API_KEY here)
│   ├── .env.example             ← Template for .env
│   │
│   ├── api/
│   │   └── v1/
│   │       └── routes.py        ← All API endpoints (/api/v1/...)
│   │
│   ├── core/
│   │   ├── config.py            ← Settings loaded from .env (pydantic-settings)
│   │   ├── logger.py            ← Structured logging setup
│   │   └── registry.py          ← Workflow registry (provider → workflow instance)
│   │
│   ├── schema/
│   │   └── workflow.py          ← Abstract base class all workflows inherit from
│   │
│   ├── services/                ← Shared low-level services
│   │   ├── ocr_engine.py        ← Smart OCR (OpenCV+Tesseract → Pillow → PyMuPDF)
│   │   ├── qr_scanner.py        ← QR code detection (pyzbar → OpenCV → preprocessed)
│   │   ├── nptel_fetcher.py     ← Fetch NPTEL portal → find PDF → OCR it
│   │   ├── comparator.py        ← 5-field weighted scoring for NPTEL
│   │   ├── browser_fetcher.py   ← Playwright headless browser fallback
│   │   └── groq_client.py       ← Shared Groq Vision AI + semantic compare
│   │
│   ├── workflows/               ← One file per platform — pure pipeline logic
│   │   ├── nptel.py             ← OCR → QR → fetch portal → compare 5 fields
│   │   ├── codetantra.py        ← OCR → scrape portal → compare 4 fields
│   │   ├── coursera.py          ← Vision AI → S3 image → URL ping → compare
│   │   └── udemy.py             ← Vision AI → S3 image → compare 4 fields
│   │
│   └── utils/
│       ├── file_utils.py        ← save_temp_file, to_image_bytes, normalize helpers
│       └── compare.py           ← _strict_compare wrapper for NPTEL
│
└── frontend/
    └── index.html               ← Full UI (no build step needed — pure HTML/CSS/JS)
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET  | `/api/v1/` | Health check |
| GET  | `/api/v1/workflows` | List all providers + metadata |
| POST | `/api/v1/verify/nptel` | Verify NPTEL certificate |
| POST | `/api/v1/verify/codetantra` | Verify CodeTantra certificate |
| POST | `/api/v1/verify/coursera` | Verify Coursera certificate |
| POST | `/api/v1/verify/udemy` | Verify Udemy certificate |

Interactive docs: `http://localhost:8000/docs`

---

## Platform Pipelines

### NPTEL
```
Upload → OCR (OpenCV+Tesseract) → QR scan → NPTEL portal
→ "Course Certificate" button → download PDF → OCR → 5-field compare
```

### CodeTantra
```
Upload → OCR (PyMuPDF+Tesseract) → extract CT####-xxx cert ID
→ scrape sathyabama.codetantra.com (3 retries) → 4-field compare
```

### Coursera
```
Upload → Vision AI (Llama 4 Scout) → download S3 JPEG
→ Vision AI on official → URL ping → AI semantic compare
```

### Udemy
```
Upload → Vision AI (Llama 4 Scout) → ensure uppercase UC-
→ download S3 JPEG → Vision AI on official → AI semantic compare
```

---

## Configuration (.env)

```env
GROQ_API_KEY=your_key_here    # Required for Coursera + Udemy
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info
```

Get a free Groq key at: https://console.groq.com

---

## Adding a New Platform

1. Create `backend/workflows/myplatform.py` extending `Workflow`
2. Implement `process(self, payload: dict) -> dict`
3. Add one line to `core/registry.py`:
   ```python
   "myplatform": MyPlatformWorkflow(),
   ```
4. Done — the API automatically exposes `/api/v1/verify/myplatform`
