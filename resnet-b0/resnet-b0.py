"""
Usage:
  python test_certificate.py --image path/to/certificate.jpg

Requirements:
  pip install torch torchvision pillow numpy matplotlib
"""

import os
import sys
import argparse
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image, ImageChops, ImageEnhance


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: ELA — Error Level Analysis
# Analogy: re-photocopying a document and checking where the ink looks "too new"
# ─────────────────────────────────────────────────────────────────────────────

def compute_ela(image_path: str, quality: int = 90, amplify: int = 15):
    original = Image.open(image_path).convert("RGB")

    # Re-save at lower quality → fresh edits compress differently
    temp = "./tmp/_ela_check.jpg"
    original.save(temp, "JPEG", quality=quality)
    recompressed = Image.open(temp)

    # Pixel-wise difference = tampering map
    ela = ImageChops.difference(original, recompressed)

    # Amplify so subtle edits become visible
    extrema = ela.getextrema()
    max_diff = max([ex[1] for ex in extrema]) or 1
    ela = ImageEnhance.Brightness(ela).enhance((255.0 / max_diff) * amplify)

    os.remove(temp)
    return original, ela


def ela_statistics(ela_image) -> dict:
    """
    Extract numerical features from ELA map.
    High mean/std = suspicious (bright patches = tampered regions).
    """
    arr = np.array(ela_image).astype(float)
    return {
        "mean"          : float(arr.mean()),
        "std"           : float(arr.std()),
        "max"           : float(arr.max()),
        "high_pixel_pct": float((arr > 128).mean() * 100),  # % of bright pixels
    }


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: ResNet-50 Feature Extraction
# Analogy: detective scans the ELA map with expert eyes to detect anomaly patterns
# ─────────────────────────────────────────────────────────────────────────────

def load_feature_extractor():
    """
    Load pretrained ResNet-50, strip the final classifier.
    Returns a model that outputs a 2048-dim feature vector.
    """
    weights = models.ResNet50_Weights.DEFAULT
    base    = models.resnet50(weights=weights)

    # Remove final FC layer → output is now a feature map
    # Analogy: the detective gives us their raw observations, not yet a verdict
    extractor = nn.Sequential(*list(base.children())[:-1])
    extractor.eval()
    return extractor


def extract_features(ela_image, extractor) -> np.ndarray:
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std =[0.229, 0.224, 0.225]),
    ])
    tensor = transform(ela_image).unsqueeze(0)
    with torch.no_grad():
        features = extractor(tensor).squeeze().numpy()
    return features


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Scoring — Combine ELA stats + Feature Anomaly Score
# Analogy: detective weighs all clues and gives a suspicion score 0–100
# ─────────────────────────────────────────────────────────────────────────────

def compute_suspicion_score(ela_stats: dict, features: np.ndarray) -> dict:
    """
    Heuristic suspicion score based on ELA statistics.

    Score breakdown (100 points total):
      40pts — ELA mean brightness  (high = suspicious)
      30pts — High pixel percentage (many bright pixels = tampered)
      30pts — Feature activation   (high variance = anomalous patterns)

    Thresholds calibrated from ELA research on document forgeries.
    """

    # Component 1: ELA mean brightness (0–40 pts)
    # Normal docs: mean < 15 | Tampered: mean > 25
    ela_mean_score = min(40, (ela_stats["mean"] / 40.0) * 40)

    # Component 2: High-brightness pixel coverage (0–30 pts)
    # Normal: < 5% | Tampered: > 15%
    high_pct_score = min(30, (ela_stats["high_pixel_pct"] / 20.0) * 30)

    # Component 3: Feature activation variance (0–30 pts)
    # High variance in ResNet features = unusual texture patterns
    feat_var       = float(np.var(features))
    feat_score     = min(30, (feat_var / 0.5) * 30)

    total = ela_mean_score + high_pct_score + feat_score
    total = min(100.0, total)

    # Verdict thresholds
    if total >= 60:
        verdict = "FAKE 🚨"
        risk    = "HIGH"
        color   = "red"
    elif total >= 35:
        verdict = "SUSPICIOUS ⚠️"
        risk    = "MEDIUM"
        color   = "orange"
    else:
        verdict = "LIKELY REAL ✅"
        risk    = "LOW"
        color   = "green"

    return {
        "total_score"      : round(total, 1),
        "verdict"          : verdict,
        "risk_level"       : risk,
        "color"            : color,
        "ela_mean_score"   : round(ela_mean_score, 1),
        "high_pixel_score" : round(high_pct_score, 1),
        "feature_score"    : round(feat_score, 1),
    }


# ─────────────────────────────────────────────────────────────────────────────
# VISUALIZATION
# ─────────────────────────────────────────────────────────────────────────────

def visualize_result(original, ela_image, ela_stats, score_info, save_path=None):
    fig = plt.figure(figsize=(16, 9), facecolor="#1a1a2e")
    gs  = gridspec.GridSpec(2, 3, figure=fig, hspace=0.4, wspace=0.3)

    title_color  = "#e0e0e0"
    label_color  = "#a0a0c0"
    verdict_color = score_info["color"]

    # ── Original image ────────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.imshow(original)
    ax1.set_title("Original Certificate", color=title_color, fontsize=11)
    ax1.axis("off")

    # ── ELA map ───────────────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.imshow(ela_image)
    ax2.set_title("ELA Map\n(bright = suspicious regions)", color=title_color, fontsize=11)
    ax2.axis("off")

    # ── ELA heatmap ────────────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[0, 2])
    ela_gray = np.array(ela_image.convert("L"))
    im = ax3.imshow(ela_gray, cmap="hot", interpolation="nearest")
    ax3.set_title("ELA Heat Map\n(red = high tampering signal)", color=title_color, fontsize=11)
    ax3.axis("off")
    plt.colorbar(im, ax=ax3, fraction=0.046, pad=0.04)

    # ── Score breakdown bar chart ─────────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.set_facecolor("#16213e")
    categories = ["ELA Brightness\n(40 pts)", "High Pixels\n(30 pts)", "Feature Anomaly\n(30 pts)"]
    scores     = [score_info["ela_mean_score"], score_info["high_pixel_score"], score_info["feature_score"]]
    max_scores = [40, 30, 30]
    colors     = ["#e94560", "#0f3460", "#533483"]

    bars = ax4.barh(categories, scores, color=colors, height=0.5)
    ax4.barh(categories, max_scores, color="#2a2a4a", height=0.5, zorder=0)
    ax4.set_xlim(0, 40)
    ax4.set_title("Score Breakdown", color=title_color, fontsize=11)
    ax4.tick_params(colors=label_color)
    for bar, score in zip(bars, scores):
        ax4.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                 f"{score:.0f}", va='center', color=title_color, fontsize=9)

    # ── ELA stats table ────────────────────────────────────────────────────
    ax5 = fig.add_subplot(gs[1, 1])
    ax5.set_facecolor("#16213e")
    ax5.axis("off")
    stats_text = (
        f"ELA STATISTICS\n"
        f"{'─'*28}\n"
        f"Mean brightness : {ela_stats['mean']:>7.1f}\n"
        f"Std deviation   : {ela_stats['std']:>7.1f}\n"
        f"Max value       : {ela_stats['max']:>7.1f}\n"
        f"High pixels     : {ela_stats['high_pixel_pct']:>6.1f}%\n\n"
        f"Thresholds\n"
        f"{'─'*28}\n"
        f"Mean > 25  →  suspicious\n"
        f"High px > 15%  →  tampered"
    )
    ax5.text(0.05, 0.95, stats_text, transform=ax5.transAxes,
             fontsize=10, verticalalignment='top',
             fontfamily='monospace', color=label_color)

    # ── Verdict panel ──────────────────────────────────────────────────────
    ax6 = fig.add_subplot(gs[1, 2])
    ax6.set_facecolor("#16213e")
    ax6.axis("off")

    # Big suspicion gauge
    theta = np.linspace(np.pi, 0, 100)
    r     = 1
    x_arc = r * np.cos(theta)
    y_arc = r * np.sin(theta)
    ax6.plot(x_arc, y_arc, color="#2a2a4a", linewidth=15, solid_capstyle='round')

    # Colored fill up to score
    fill_pct   = score_info["total_score"] / 100.0
    theta_fill = np.linspace(np.pi, np.pi - fill_pct * np.pi, 100)
    ax6.plot(r * np.cos(theta_fill), r * np.sin(theta_fill),
             color=verdict_color, linewidth=15, solid_capstyle='round')

    ax6.text(0, 0.1, f"{score_info['total_score']:.0f}", ha='center', va='center',
             fontsize=36, fontweight='bold', color=verdict_color)
    ax6.text(0, -0.3, "/ 100", ha='center', fontsize=14, color=label_color)
    ax6.text(0, -0.6, score_info["verdict"], ha='center', fontsize=15,
             fontweight='bold', color=verdict_color)
    ax6.text(0, -0.85, f"Risk: {score_info['risk_level']}", ha='center',
             fontsize=11, color=label_color)

    ax6.set_xlim(-1.3, 1.3)
    ax6.set_ylim(-1.1, 1.2)
    ax6.set_title("Suspicion Score", color=title_color, fontsize=11)

    # ── Main title ─────────────────────────────────────────────────────────
    fig.suptitle("🔍 Certificate Forgery Analysis", fontsize=16,
                 color=title_color, fontweight='bold', y=0.98)

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        print(f"\n  📊 Visualization saved → {save_path}")
    else:
        plt.show()
    plt.close()


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def test_certificate(image_path: str, ela_quality: int = 90, save_viz: bool = True):
    print("\n" + "=" * 55)
    print("  🔍 CERTIFICATE FORGERY TESTER")
    print("=" * 55)
    print(f"  File : {os.path.basename(image_path)}")

    # Step 1: ELA
    print("\n  [1/3] Running ELA analysis...")
    original, ela_image = compute_ela(image_path, quality=ela_quality)
    ela_stats = ela_statistics(ela_image)
    print(f"        ELA mean={ela_stats['mean']:.1f}  std={ela_stats['std']:.1f}  "
          f"high_px={ela_stats['high_pixel_pct']:.1f}%")

    # Step 2: Feature extraction
    print("  [2/3] Extracting ResNet-50 features...")
    extractor = load_feature_extractor()
    features  = extract_features(ela_image, extractor)
    print(f"        Feature vector: {features.shape[0]} dims  "
          f"var={np.var(features):.4f}")

    # Step 3: Score
    print("  [3/3] Computing suspicion score...")
    score_info = compute_suspicion_score(ela_stats, features)

    # Print result
    print("\n  ┌───────────────────────────────────────────┐")
    print(f"  │  VERDICT     : {score_info['verdict']:<28}│")
    print(f"  │  RISK LEVEL  : {score_info['risk_level']:<28}│")
    print(f"  │  TOTAL SCORE : {score_info['total_score']:<5.1f} / 100                   │")
    print("  ├───────────────────────────────────────────┤")
    print(f"  │  ELA brightness score  : {score_info['ela_mean_score']:>5.1f} / 40        │")
    print(f"  │  High-pixel coverage   : {score_info['high_pixel_score']:>5.1f} / 30        │")
    print(f"  │  Feature anomaly score : {score_info['feature_score']:>5.1f} / 30        │")
    print("  └───────────────────────────────────────────┘")

    # Visualize
    if save_viz:
        viz_path = os.path.splitext(image_path)[0] + "_analysis.png"
        visualize_result(original, ela_image, ela_stats, score_info, save_path=viz_path)

    return score_info


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test a single certificate for forgery")
    parser.add_argument("--image",       required=True,        help="Path to certificate image")
    parser.add_argument("--ela_quality", type=int, default=90, help="ELA JPEG quality (default 90)")
    parser.add_argument("--no_viz",      action="store_true",  help="Skip visualization")
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"  ❌ File not found: {args.image}")
        sys.exit(1)

    test_certificate(args.image, ela_quality=args.ela_quality, save_viz=not args.no_viz)