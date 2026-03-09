# 🔍 Certificate Forgery Analysis (ResNet-50 + ELA)

A Python-based forensic tool designed to detect digital tampering in certificates and official documents using **Error Level Analysis (ELA)** and **Deep Learning feature extraction**.

## 🚀 Overview

This project provides an automated suspicious region detection system for digital images. It combines traditional image forensics (ELA) with modern computer vision (ResNet-50) to generate a "Suspicion Score" (0–100) and a visual forensic report.

---

## ✨ Features

- **Error Level Analysis (ELA):** Detects non-uniform compression levels in JPEG images, highlighting regions that have been edited or resaved.
- **Deep Feature Extraction:** Uses a pre-trained **ResNet-50** model to analyze texture anomalies in the ELA map.
- **Automated Scoring:** Generates a probability-based verdict (Real, Suspicious, or Fake) based on statistical thresholds.
- **Visual Forensic Report:** Produces a multi-panel dashboard including:
  - Original Image vs. ELA Map
  - Heatmap of tampered regions
  - Statistical breakdown and gauge visualization
- **Command-line Interface:** Simple CLI for batch processing or single-file analysis.

---

## 🛠️ How It Works

The detection pipeline consists of three primary stages:

### 1. Error Level Analysis (ELA)
When a JPEG image is modified and resaved, the modified areas undergo a different level of compression compared to the original parts. The tool re-saves the image at a specific quality (e.g., 90%) and calculates the pixel-wise difference. Bright regions in the ELA map indicate potential tampering.

### 2. Deep Learning Feature Analysis
The ELA map is passed through a **ResNet-50** neural network (pre-trained on ImageNet). Instead of classification, the tool uses the 2048-dimensional feature vector from the penultimate layer. High variance in these features often correlates with irregular digital artifacts that are invisible to the naked eye.

### 3. Suspicion Scoring & Verdict
A heuristic algorithm weights the following factors:
- **ELA Mean Brightness:** Overall signal strength of the difference map.
- **High-Pixel Percentage:** The density of highly suspicious (bright) clusters.
- **Feature Anomaly Score:** Mathematical variance in the neural network's observations.

**Verdict Thresholds:**
- **< 35:** Likely Real ✅ (Low Risk)
- **35 - 60:** Suspicious ⚠️ (Medium Risk)
- **> 60:** FAKE 🚨 (High Risk)

---

## 📦 Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/resnet-b0.git
   cd resnet-b0
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 💻 Usage

Analyze a certificate by providing the path to the image:

```bash
python resnet-b0.py --image path/to/your/certificate.jpg
```

### Optional Arguments:
- `--ela_quality [INT]`: Set the JPEG quality for ELA comparison (default: 90).
- `--no_viz`: Run analysis without generating the visual report.

### Output:
The tool will print a breakdown to the console and save a visualization file named `[image_name]_analysis.png` in the same directory.

---

## ⚠️ Disclaimer

This tool is designed for research and educational purposes. Forensic analysis results should be interpreted as a "probability of tampering" rather than absolute proof. For critical applications, always combine these results with manual inspection and metadata analysis.

