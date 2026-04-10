"""
NPTEL Certificate Batch Verifier
=================================
Scans the NPTL-CERTIFICATES folder, processes every PDF across all section
subfolders (A1, A2, …), runs the full NPTELWorkflow pipeline for each
certificate, and writes a clean CSV report.

Folder structure expected:
    NPTL-CERTIFICATES/
    ├── A1/
    │   ├── 44110003.pdf
    │   └── 44110008.pdf
    ├── A2/
    │   └── ...
    └── ...

Usage:
    python batch_verifier.py
"""

import os
import csv
import time
import shutil
import logging
import tempfile
import traceback
from datetime import datetime
from pathlib import Path

# ─── Your existing workflow ───────────────────────────────────────────────────
from workflows.nptel import NPTELWorkflow


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

CERT_FOLDER = os.environ.get("CERT_FOLDER", "./NPTL-CERTIFICATES")
OUTPUT_CSV  = "nptel_batch_report.csv"
LOG_FILE    = "batch_verifier.log"
DELAY_SEC   = 1.5   # polite delay between NPTEL web requests


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
#  CSV COLUMNS  — only the fields that actually matter
# ══════════════════════════════════════════════════════════════════════════════

CSV_COLUMNS = [
    "S.No",
    "Timestamp",
    "Section",
    "PDF File Name",
    "Candidate Name",
    "Course Name",
    "Roll / Cert ID",
    "Course Duration",
    "Issue Date",
    "QR Found",
    "Verification Status",   # VALID / FAKE / NO_QR_FOUND / ERROR / NO_OFFICIAL_TEXT
    "Validation Status",     # PASS  / FAIL / NEEDS REVIEW
    "Failed Fields",
    "Match Score",
    "Time Taken (sec)",
    "Error Detail",
]


# ══════════════════════════════════════════════════════════════════════════════
#  COLLECT PDFs
#  FIX: handles both .pdf and .PDF (uppercase) extensions — your data has both
# ══════════════════════════════════════════════════════════════════════════════

def collect_pdfs(root: str) -> list[dict]:
    """
    Walk root -> subfolders -> PDFs (one level deep).
    Case-insensitive extension match so .PDF is not missed.
    PDFs directly in root are labelled section='root'.
    """
    entries = []
    root_path = Path(root)

    if not root_path.exists():
        log.error(
            f"Folder not found: '{root}'. "
            "Update CERT_FOLDER at the top of the script."
        )
        return entries

    for item in sorted(root_path.iterdir()):
        if item.is_dir():
            section = item.name
            pdfs = sorted(
                p for p in item.iterdir()
                if p.is_file() and p.suffix.lower() == ".pdf"
            )
            for pdf in pdfs:
                entries.append({
                    "section":   section,
                    "filename":  pdf.name,
                    "full_path": str(pdf.resolve()),
                })
        elif item.is_file() and item.suffix.lower() == ".pdf":
            entries.append({
                "section":   "root",
                "filename":  item.name,
                "full_path": str(item.resolve()),
            })

    log.info(
        f"Collected {len(entries)} PDF(s) across "
        f"{len(set(e['section'] for e in entries))} section(s)."
    )
    return entries


# ══════════════════════════════════════════════════════════════════════════════
#  VALIDATION STATUS MAPPING
#
#  FIX: The old code checked for "GENUINE" — that was WRONG.
#  Your _strict_compare (utils/compare.py) maps the comparator's "GENUINE"
#  verdict to "VALID" before it reaches the workflow response dict.
#  Confirmed from your actual CSV output: verification_status = "VALID" not "GENUINE".
# ══════════════════════════════════════════════════════════════════════════════

def derive_validation_status(verification_status: str) -> str:
    """
    VALID            -> PASS
    FAKE             -> FAIL
    NO_QR_FOUND      -> NEEDS REVIEW
    NO_OFFICIAL_TEXT -> NEEDS REVIEW
    ERROR / UNKNOWN  -> NEEDS REVIEW
    """
    vs = str(verification_status).upper().strip()
    if vs == "VALID":
        return "PASS"
    if vs == "FAKE":
        return "FAIL"
    return "NEEDS REVIEW"


# ══════════════════════════════════════════════════════════════════════════════
#  PROCESS ONE PDF
# ══════════════════════════════════════════════════════════════════════════════

workflow = NPTELWorkflow()


def process_single_pdf(entry: dict) -> dict:
    """
    Run the full NPTEL verification pipeline on one PDF.
    Returns a flat dict whose keys exactly match CSV_COLUMNS.
    """
    row      = {col: "" for col in CSV_COLUMNS}
    tmp_path = None
    start    = time.time()

    try:
        # Copy to temp — workflow.process() deletes the file in its finally
        # block, so we must give it a disposable copy not the original.
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            shutil.copy2(entry["full_path"], tmp.name)
            tmp_path = tmp.name

        # ── Run the full pipeline ─────────────────────────────────────────────
        result = workflow.process({"path": tmp_path, "verf_url": ""})

        # ── Unpack ───────────────────────────────────────────────────────────
        qr         = result.get("qr",              {})
        comparison = result.get("comparison",      {})
        u_fields   = result.get("uploaded_fields", {})
        o_fields   = result.get("official_fields", {})

        # verification_status from your _strict_compare:
        # VALID / FAKE / NO_QR_FOUND / ERROR / NO_OFFICIAL_TEXT
        verification_status = str(
            comparison.get("verification_status", "UNKNOWN")
        ).upper().strip()

        score = comparison.get("score", 0.0)

        # Handle both key names that _strict_compare may use
        failed_fields = (
            comparison.get("failed_fields")
            or comparison.get("failed_field_names")
            or []
        )

        # Use official fields (verified from NPTEL portal) as the source of
        # truth; fall back to uploaded fields if official not available.
        candidate_name  = (o_fields.get("candidate_name")  or u_fields.get("candidate_name")  or "").strip()
        course_name     = (o_fields.get("course_name")     or u_fields.get("course_name")     or "").strip()
        roll_id         = (o_fields.get("roll_or_cert_id") or u_fields.get("roll_or_cert_id") or "").strip()
        course_duration = (o_fields.get("course_duration") or u_fields.get("course_duration") or "").strip()
        issue_date      = (o_fields.get("issue_date")      or u_fields.get("issue_date")      or "").strip()

        # ── Populate row ──────────────────────────────────────────────────────
        row["QR Found"]            = "Yes" if qr.get("found") else "No"
        row["Candidate Name"]      = candidate_name
        row["Course Name"]         = course_name
        row["Roll / Cert ID"]      = roll_id
        row["Course Duration"]     = course_duration
        row["Issue Date"]          = issue_date
        row["Verification Status"] = verification_status
        row["Validation Status"]   = derive_validation_status(verification_status)
        row["Failed Fields"]       = ", ".join(failed_fields) if failed_fields else ""
        row["Match Score"]         = round(score, 4)
        row["Error Detail"]        = str(result.get("error") or "")

    except Exception as exc:
        traceback.print_exc()
        row["Verification Status"] = "ERROR"
        row["Validation Status"]   = "NEEDS REVIEW"
        row["Error Detail"]        = str(exc)
        log.error(f"  ✗ Exception on '{entry['filename']}': {exc}")

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    # Metadata — written regardless of success or failure
    elapsed               = round(time.time() - start, 2)
    row["Timestamp"]      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row["Section"]        = entry["section"]
    row["PDF File Name"]  = entry["filename"]
    row["Time Taken (sec)"] = elapsed

    return row


# ══════════════════════════════════════════════════════════════════════════════
#  BATCH LOOP + CSV WRITER
# ══════════════════════════════════════════════════════════════════════════════

def run_batch():
    pdf_list = collect_pdfs(CERT_FOLDER)

    if not pdf_list:
        log.error("No PDFs found. Check CERT_FOLDER path.")
        return

    counters = {"PASS": 0, "FAIL": 0, "NEEDS REVIEW": 0}

    log.info("=" * 60)
    log.info(f"  NPTEL BATCH VERIFIER — {len(pdf_list)} certificate(s)")
    log.info(f"  Folder  -> {CERT_FOLDER}")
    log.info(f"  Output  -> {OUTPUT_CSV}")
    log.info("=" * 60)

    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()

        current_section = None

        for idx, entry in enumerate(pdf_list, start=1):

            if entry["section"] != current_section:
                current_section = entry["section"]
                log.info(f"\n  -- Section: {current_section} --")

            log.info(f"  [{idx:>3}/{len(pdf_list)}] {entry['filename']}")

            row         = process_single_pdf(entry)
            row["S.No"] = idx

            writer.writerow(row)
            csvfile.flush()   # write immediately — crash safe

            val  = row.get("Validation Status", "NEEDS REVIEW")
            ver  = row.get("Verification Status", "")
            score_val = row.get("Match Score", "")
            counters[val] = counters.get(val, 0) + 1

            icon = {"PASS": "[PASS]", "FAIL": "[FAIL]", "NEEDS REVIEW": "[REVIEW]"}.get(val, "[?]")
            log.info(
                f"       {icon}  ver={ver:<20}  "
                f"score={score_val}  time={row['Time Taken (sec)']}s"
            )

            time.sleep(DELAY_SEC)

    log.info(f"\n{'='*60}")
    log.info("  BATCH COMPLETE")
    log.info(f"{'='*60}")
    log.info(f"  Total processed  : {len(pdf_list)}")
    log.info(f"  PASS             : {counters.get('PASS', 0)}")
    log.info(f"  FAIL             : {counters.get('FAIL', 0)}")
    log.info(f"  NEEDS REVIEW     : {counters.get('NEEDS REVIEW', 0)}")
    log.info(f"  Report saved to  : {OUTPUT_CSV}")
    log.info(f"  Log saved to     : {LOG_FILE}")
    log.info(f"{'='*60}\n")


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    run_batch()
