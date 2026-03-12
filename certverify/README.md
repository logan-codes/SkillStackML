# CertVerify — Certificate Verification System

Automatically verify certificates from Udemy, Coursera, NPTEL and more.
Upload a certificate image/PDF + paste the official verification URL — the
system extracts text via OCR, scrapes the official page, and compares them.

---

## Project Structure

```
certverify/
├── backend/
│   ├── main.py            FastAPI server  →  port 8000
│   ├── ocr_engine.py      OpenCV / Pillow + pytesseract OCR
│   ├── web_fetcher.py     requests + BeautifulSoup scraper
│   ├── comparator.py      Field extraction + fuzzy scoring
│   └── requirements.txt
├── frontend/
│   ├── public/index.html
│   └── src/
│       ├── App.js         React UI (native fetch, no axios)
│       ├── App.css
│       ├── index.js
│       └── index.css
├── package.json           Root — concurrently runs both servers
└── README.md
```

---

## Prerequisites (install once)

### Node.js 18+
https://nodejs.org/en/download

### Python 3.9+
https://www.python.org/downloads

### Tesseract OCR
```bash
# Windows  → https://github.com/UB-Mannheim/tesseract/wiki
#            Install, then add to PATH: C:\Program Files\Tesseract-OCR

# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt install tesseract-ocr
```
> If Tesseract is not installed, the system falls back to mock OCR data
> automatically — you can still test the full UI and URL comparison flow.

---

## Setup (run once)

```bash
# 1. Install Node packages
npm run setup

# 2. Install Python packages  (numpy<2 MUST be installed first)
pip install "numpy<2"
pip install -r backend/requirements.txt
```

---

## Start the application

```bash
npm start
```

Opens:
- Frontend  →  http://localhost:3000
- Backend   →  http://localhost:8000
- API docs  →  http://localhost:8000/docs

---

## Run manually (two terminals)

```bash
# Terminal 1 — backend
cd backend
python main.py

# Terminal 2 — frontend
cd frontend
npm install
npm start
```

---

## How to use

1. Go to http://localhost:3000
2. Upload a certificate (PNG / JPG / PDF)
3. Paste the official verification URL (optional but recommended)
   - Udemy:    https://ude.my/UC-xxxxxxxx
   - Coursera: https://www.coursera.org/verify/xxxxxxxxxx
   - NPTEL:    URL printed on the certificate
4. Click **Verify Certificate**
5. View results — OCR text, field comparison, match score, VALID / FAKE verdict

---

## Verification scoring

| Field            | Weight |
|------------------|--------|
| Certificate ID   | 35%    |
| Student name     | 25%    |
| Course title     | 20%    |
| Issuer           | 10%    |
| Completion date  | 10%    |

Final score = 70% weighted field score + 30% full-text similarity.
Score >= 60% → **VALID**, Score < 60% → **FAKE**

---

## Troubleshooting

**TesseractNotFoundError on Windows**
Add Tesseract to your PATH, or add this line at the top of `backend/ocr_engine.py`:
```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

**numpy / cv2 crash on startup**
```bash
pip install "numpy<2"
pip install opencv-python-headless==4.9.0.80
```

**Port already in use**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

**CORS error in browser**
Make sure backend runs on port 8000 and frontend on port 3000.

**URL always shows NO_URL_PROVIDED**
Open browser DevTools → Console — you should see:
```
[CertVerify] verification_url = https://ude.my/...
```
If it shows `(none)`, the URL field was empty when you clicked verify.
