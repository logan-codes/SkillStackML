import React, { useState, useRef, useCallback } from "react";
import "./App.css";

var API = "http://localhost:8000";

/* ── helpers ── */
function cx() {
  return Array.from(arguments).filter(Boolean).join(" ");
}

/* ── Step indicator ── */
function StepBadge({ n, label, status }) {
  // status: idle | running | ok | warn | fail
  var icon =
    { idle: n, running: "…", ok: "✓", warn: "⚠", fail: "✗" }[status] || n;
  return (
    <div className={cx("step-badge", "step-" + status)}>
      <span className="step-num">{icon}</span>
      <span className="step-label">{label}</span>
    </div>
  );
}

/* ── OCR Status block ── */
function OcrBlock({ title, ocr, tag }) {
  var s = useState(false);
  var open = s[0];
  var setOpen = s[1];
  if (!ocr) return null;
  var ok = ocr.success;
  return (
    <div className={cx("info-block", ok ? "block-ok" : "block-fail")}>
      <div
        className="info-block-header"
        onClick={function () {
          setOpen(!open);
        }}
      >
        <span className={cx("tag", tag)}>{title}</span>
        <span className={cx("status-dot", ok ? "dot-ok" : "dot-fail")}>
          {ok ? "✓ OCR performed" : "✗ OCR not performed"}
        </span>
        {ok && <span className="method-pill">{ocr.method}</span>}
        <span className="toggle">{open ? "▲" : "▼"}</span>
      </div>
      <p className="info-detail">{ocr.detail}</p>
      {open && ok && ocr.text && <pre className="text-preview">{ocr.text}</pre>}
    </div>
  );
}

/* ── QR block ── */
function QrBlock({ qr }) {
  if (!qr) return null;
  var ok = qr.found;
  return (
    <div className={cx("info-block", ok ? "block-ok" : "block-warn")}>
      <div className="info-block-header">
        <span className="tag tag-qr">QR Code</span>
        <span className={cx("status-dot", ok ? "dot-ok" : "dot-warn")}>
          {ok ? "✓ QR found & decoded" : "✗ No QR code found"}
        </span>
        {ok && qr.method && <span className="method-pill">{qr.method}</span>}
      </div>
      {ok && (
        <p className="info-detail">
          <strong>Decoded URL: </strong>
          <a href={qr.url} target="_blank" rel="noreferrer" className="qr-url">
            {qr.url}
          </a>
        </p>
      )}
      {!ok && <p className="info-detail">{qr.detail}</p>}
    </div>
  );
}

/* ── Official block ── */
function OfficialBlock({ official }) {
  var s = useState(false);
  var open = s[0];
  var setOpen = s[1];
  if (!official) return null;
  var ok = official.success;
  var steps = official.steps || [];
  return (
    <div className={cx("info-block", ok ? "block-ok" : "block-fail")}>
      <div
        className="info-block-header"
        onClick={function () {
          setOpen(!open);
        }}
      >
        <span className="tag tag-off">Official NPTEL Certificate</span>
        <span className={cx("status-dot", ok ? "dot-ok" : "dot-fail")}>
          {ok ? "✓ PDF fetched & OCR'd" : "✗ Fetch failed"}
        </span>
        {ok && official.ocr_method && (
          <span className="method-pill">{official.ocr_method}</span>
        )}
        <span className="toggle">{open ? "▲" : "▼"}</span>
      </div>

      {/* Step-by-step log */}
      {steps.length > 0 && (
        <div className="steps-log">
          {steps.map(function (step, i) {
            var isOk =
              step.indexOf("HTTP 200") !== -1 ||
              step.indexOf("success") !== -1 ||
              step.indexOf("Found") !== -1 ||
              step.indexOf("saved") !== -1;
            var isFail =
              step.indexOf("failed") !== -1 ||
              step.indexOf("Could not") !== -1 ||
              step.indexOf("No ") !== -1;
            return (
              <div
                key={i}
                className={cx(
                  "step-log-row",
                  isOk && "log-ok",
                  isFail && "log-fail",
                )}
              >
                <span className="log-dot">
                  {isOk ? "✓" : isFail ? "✗" : "›"}
                </span>
                <span className="log-text">{step}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* PDF link */}
      {official.pdf_url && (
        <p className="info-detail">
          <span style={{ color: "var(--muted)" }}>
            Course Certificate PDF:{" "}
          </span>
          <a
            href={official.pdf_url}
            target="_blank"
            rel="noreferrer"
            className="qr-url"
          >
            {official.pdf_url}
          </a>
        </p>
      )}

      <p className="info-detail">{official.detail}</p>

      {open && ok && official.text && (
        <pre className="text-preview">{official.text}</pre>
      )}
    </div>
  );
}

/* ── Field row ── */
function FieldRow({ field, data }) {
  // similarity null = field not found in either cert
  var notFound = data.similarity === null || data.similarity === undefined;
  var sim = notFound ? null : Math.round(data.similarity * 100);
  var matched = data.match;
  return (
    <div
      className={cx(
        "field-row",
        notFound ? "field-unknown" : matched ? "field-match" : "field-mismatch",
      )}
    >
      <div className="field-header">
        <span className="field-label">
          {data.label || field.replace(/_/g, " ")}
        </span>
        <span
          className={cx(
            "field-icon",
            notFound ? "icon-unknown" : matched ? "icon-ok" : "icon-fail",
          )}
        >
          {notFound ? "?" : matched ? "✓" : "✗"}
        </span>
        {!notFound && <span className="field-sim">{sim}%</span>}
        {notFound && <span className="field-sim muted">not found</span>}
        <span className="field-weight">
          weight {Math.round((data.weight || 0) * 100)}%
        </span>
      </div>
      <div className="field-vals">
        <div className="field-val">
          <span className="fv-tag tag-up">uploaded</span>
          <span className="fv-text">{data.uploaded || "—"}</span>
        </div>
        <div className="field-val">
          <span className="fv-tag tag-off">official</span>
          <span className="fv-text">{data.official || "—"}</span>
        </div>
      </div>
    </div>
  );
}

/* ── Score ring ── */
function ScoreRing({ score }) {
  var pct = Math.round(score * 100);
  var r = 38;
  var circ = 2 * Math.PI * r;
  var dash = (pct / 100) * circ;
  var color = pct >= 80 ? "#10b981" : pct >= 60 ? "#f59e0b" : "#ef4444";
  return (
    <div className="score-ring-wrap">
      <svg width="96" height="96" viewBox="0 0 100 100">
        <circle
          cx="50"
          cy="50"
          r={r}
          fill="none"
          stroke="#252a35"
          strokeWidth="8"
        />
        <circle
          cx="50"
          cy="50"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={dash + " " + circ}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
          style={{ transition: "stroke-dasharray 1s ease" }}
        />
      </svg>
      <div className="score-label">
        <span className="score-pct" style={{ color }}>
          {pct}%
        </span>
        <span className="score-sub">match</span>
      </div>
    </div>
  );
}

/* ── Verdict ── */
function Verdict({ cmp }) {
  var vs = cmp.verification_status;
  var failed = cmp.failed_fields || [];
  var missing = cmp.not_found || [];

  var fakeDesc =
    cmp.reason ||
    (failed.length ? "Mismatch in: " + failed.join(", ") : "") ||
    "Certificate does not match the official NPTEL record.";
  var unknownDesc =
    cmp.reason ||
    (missing.length
      ? "Could not extract: " + missing.join(", ")
      : "Unexpected state.");

  var configs = {
    VALID: {
      cls: "verdict-valid",
      icon: "✓",
      title: "GENUINE",
      desc: "All 5 fields match the official NPTEL record.",
    },
    FAKE: {
      cls: "verdict-fake",
      icon: "✗",
      title: "FAKE / TAMPERED",
      desc: fakeDesc,
    },
    NO_QR_FOUND: {
      cls: "verdict-warn",
      icon: "⚠",
      title: "NO QR FOUND",
      desc: cmp.reason,
    },
    OCR_FAILED: {
      cls: "verdict-warn",
      icon: "⚠",
      title: "OCR FAILED",
      desc: cmp.reason,
    },
    NO_OFFICIAL_TEXT: {
      cls: "verdict-warn",
      icon: "⚠",
      title: "NO OFFICIAL TEXT",
      desc: cmp.reason,
    },
    ERROR: { cls: "verdict-warn", icon: "⚠", title: "ERROR", desc: cmp.reason },
    UNKNOWN: {
      cls: "verdict-warn",
      icon: "⚠",
      title: "UNVERIFIED",
      desc: unknownDesc,
    },
  };
  var cfg = configs[vs] || configs.UNKNOWN;
  return (
    <div className={cx("verdict-card", cfg.cls)}>
      <div className="verdict-left">
        <span className="verdict-icon">{cfg.icon}</span>
        <div>
          <div className="verdict-title">{cfg.title}</div>
          <div className="verdict-desc">{cfg.desc}</div>
          {failed.length > 0 && (
            <div className="verdict-failed-list">
              {failed.map(function (f) {
                return (
                  <span key={f} className="verdict-failed-pill">
                    ✗ {f}
                  </span>
                );
              })}
            </div>
          )}
        </div>
      </div>
      {cmp.can_compare && cmp.score > 0 && <ScoreRing score={cmp.score} />}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════
   Main App
══════════════════════════════════════════════════════════ */
export default function App() {
  var s1 = useState(null);
  var file = s1[0];
  var setFile = s1[1];
  var s2 = useState(null);
  var preview = s2[0];
  var setPreview = s2[1];
  var s3 = useState(false);
  var loading = s3[0];
  var setLoading = s3[1];
  var s4 = useState(null);
  var result = s4[0];
  var setResult = s4[1];
  var s5 = useState(null);
  var error = s5[0];
  var setError = s5[1];
  var s6 = useState(false);
  var dragOver = s6[0];
  var setDragOver = s6[1];
  var s7 = useState("");
  var manualUrl = s7[0];
  var setManualUrl = s7[1];
  var s8 = useState(false);
  var showManual = s8[0];
  var setShowManual = s8[1];

  var fileRef = useRef(null);

  var handleFile = useCallback(function (f) {
    if (!f) return;
    setFile(f);
    setResult(null);
    setError(null);
    if (f.type && f.type.startsWith("image/")) {
      var r = new FileReader();
      r.onload = function (e) {
        setPreview(e.target.result);
      };
      r.readAsDataURL(f);
    } else {
      setPreview(null);
    }
  }, []);

  var onDrop = useCallback(
    function (e) {
      e.preventDefault();
      setDragOver(false);
      var f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
      if (f) handleFile(f);
    },
    [handleFile],
  );

  function submit() {
    if (!file) {
      setError("Please upload an NPTEL certificate.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);

    var fd = new FormData();
    fd.append("file", file, file.name);
    if (showManual && manualUrl.trim()) {
      fd.append("manual_url", manualUrl.trim());
    }

    console.log("[CertVerify] submitting", file.name);

    fetch(API + "/verify", { method: "POST", body: fd })
      .then(function (r) {
        return r.json().then(function (d) {
          return { ok: r.ok, data: d };
        });
      })
      .then(function (res) {
        console.log("[CertVerify] result:", res.data);
        if (!res.ok)
          throw new Error((res.data && res.data.detail) || "Server error");
        setResult(res.data);
        setLoading(false);
      })
      .catch(function (err) {
        setError(
          err.message || "Request failed. Is backend running on port 8000?",
        );
        setLoading(false);
      });
  }

  function reset() {
    setFile(null);
    setPreview(null);
    setResult(null);
    setError(null);
    setManualUrl("");
    setShowManual(false);
  }

  var dropCls = cx("drop-zone", dragOver && "drag-active", file && "has-file");

  /* derive pipeline step statuses for the header progress bar */
  var steps = {
    ocr: !result
      ? "idle"
      : result.uploaded_ocr && result.uploaded_ocr.success
        ? "ok"
        : "fail",
    qr: !result ? "idle" : result.qr && result.qr.found ? "ok" : "warn",
    fetch: !result
      ? "idle"
      : result.official && result.official.success
        ? "ok"
        : "fail",
    compare: !result
      ? "idle"
      : result.comparison && result.comparison.can_compare
        ? result.comparison.verification_status === "VALID"
          ? "ok"
          : "fail"
        : "warn",
  };
  if (loading) {
    steps.ocr = "running";
  }

  // Use field_matches (new comparator) with fallback to field_comparison (legacy)
  var fieldData =
    result && result.comparison
      ? result.comparison.field_matches ||
        result.comparison.field_comparison ||
        {}
      : {};
  var fieldKeys = Object.keys(fieldData);

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="app-header">
        <div className="header-top">
          <div className="logo">
            <span className="logo-icon">◈</span>
            <div>
              <div className="logo-title">
                CertVerify <span className="logo-nptel">NPTEL</span>
              </div>
              <div className="logo-sub">
                Certificate Verification via QR Code
              </div>
            </div>
          </div>
          {/* Pipeline steps */}
          <div className="pipeline">
            <StepBadge
              n="1"
              label="OCR"
              status={loading ? "running" : steps.ocr}
            />
            <span className="pipe-arrow">→</span>
            <StepBadge
              n="2"
              label="QR Scan"
              status={loading ? "running" : steps.qr}
            />
            <span className="pipe-arrow">→</span>
            <StepBadge
              n="3"
              label="Fetch"
              status={loading ? "running" : steps.fetch}
            />
            <span className="pipe-arrow">→</span>
            <StepBadge
              n="4"
              label="Compare"
              status={loading ? "running" : steps.compare}
            />
          </div>
        </div>
        <div className="header-line" />
      </header>

      <main className="main">
        {/* ── Upload ── */}
        <section>
          <div className="section-label">
            <span className="step-pill">01</span>
            Upload NPTEL Certificate
          </div>
          <div
            className={dropCls}
            onDrop={onDrop}
            onDragOver={function (e) {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={function () {
              setDragOver(false);
            }}
            onClick={function () {
              if (!file && fileRef.current) fileRef.current.click();
            }}
          >
            <input
              ref={fileRef}
              type="file"
              accept="image/*,.pdf"
              style={{ display: "none" }}
              onChange={function (e) {
                if (e.target.files && e.target.files[0])
                  handleFile(e.target.files[0]);
              }}
            />
            {file ? (
              <div className="file-info">
                {preview ? (
                  <img src={preview} alt="cert" className="file-thumb" />
                ) : (
                  <div className="pdf-badge">PDF</div>
                )}
                <div className="file-meta">
                  <span className="file-name">{file.name}</span>
                  <span className="file-size">
                    {(file.size / 1024).toFixed(1)} KB
                  </span>
                  <button
                    className="btn-ghost"
                    onClick={function (e) {
                      e.stopPropagation();
                      reset();
                    }}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ) : (
              <div className="drop-prompt">
                <div className="drop-arrow">↑</div>
                <p className="drop-text">
                  Drop NPTEL certificate here or{" "}
                  <span className="drop-link">browse</span>
                </p>
                <p className="drop-hint">
                  PNG · JPG · PDF — must contain a QR code
                </p>
              </div>
            )}
          </div>

          {/* Manual URL fallback */}
          <div style={{ marginTop: 10 }}>
            <button
              className="btn-link"
              onClick={function () {
                setShowManual(!showManual);
              }}
            >
              {showManual
                ? "▲ Hide manual URL"
                : "▼ QR not readable? Enter NPTEL URL manually"}
            </button>
          </div>
          {showManual && (
            <div className="manual-wrap">
              <input
                className="manual-input"
                type="text"
                placeholder="https://archive.nptel.ac.in/noc/Ecertificate/?q=..."
                value={manualUrl}
                onChange={function (e) {
                  setManualUrl(e.target.value);
                }}
              />
            </div>
          )}
        </section>

        {/* ── Submit ── */}
        <section className="submit-row">
          <button
            className={cx("btn-verify", loading && "loading")}
            onClick={submit}
            disabled={loading || !file}
          >
            {loading ? (
              <>
                <span className="spinner" /> Scanning &amp; Verifying…
              </>
            ) : (
              <>◈ Scan QR &amp; Verify</>
            )}
          </button>
          {error && <div className="error-msg">⚠ {error}</div>}
        </section>

        {/* ── Results ── */}
        {result && (
          <section className="results">
            <div className="results-header">
              <div className="section-label">
                <span className="step-pill">02</span>
                Results
              </div>
              <button className="btn-ghost" onClick={reset}>
                ↺ New Check
              </button>
            </div>

            {/* Verdict */}
            <Verdict cmp={result.comparison} />

            {/* 4 pipeline info blocks */}
            <div className="pipeline-results">
              <OcrBlock
                title="Step 1 — Uploaded Certificate OCR"
                ocr={result.uploaded_ocr}
                tag="tag-up"
              />
              <QrBlock qr={result.qr} />
              <OfficialBlock official={result.official} />
            </div>

            {/* 5-field comparison */}
            {result.comparison.can_compare && fieldKeys.length > 0 && (
              <div className="fields-section">
                <h3 className="block-title">
                  Certificate Field Verification
                  <span className="fields-found">
                    {
                      fieldKeys.filter(
                        (k) => fieldData[k] && fieldData[k].match === true,
                      ).length
                    }{" "}
                    / {fieldKeys.length} fields matched
                  </span>
                </h3>
                <div className="fields-grid">
                  {fieldKeys.map(function (k) {
                    return <FieldRow key={k} field={k} data={fieldData[k]} />;
                  })}
                </div>
              </div>
            )}

            {/* Raw JSON */}
            <details className="raw-json">
              <summary>View Raw API Response</summary>
              <pre>{JSON.stringify(result, null, 2)}</pre>
            </details>
          </section>
        )}
      </main>

      <footer className="app-footer">
        <span>CertVerify NPTEL v2.0</span>
        <span className="sep">·</span>
        <span>QR Scan → OCR → Official Fetch → Strict Compare</span>
      </footer>
    </div>
  );
}
