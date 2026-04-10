from ultralytics import YOLO
from multiprocessing import freeze_support
import cv2
import torch
import torchvision.models as models
import torchvision.transforms as T
from PIL import Image
import os
from rembg import remove

MODEL_PATH = r"E:\Coding\SkillStack\ml\CampusCred\models\yolo\yolo11n.pt"

class YOLO11n:
    def __init__(self, model_path = "yolo11n.pt"):
        self.model = YOLO(model_path)  # load a pretrained model (recommended for training)
        if model_path == "yolo11n.pt":
            self.model.save(MODEL_PATH)
    
    def train(self, train_data_path = r"data\data.yaml", epochs = 100, imgsz = 640, device = 0, batch=8, workers=2, save_path = "runs/detect/train_signature"):
        # Train the model
        freeze_support()
        results = self.model.train(data=train_data_path, epochs=epochs, imgsz=imgsz, device=device, batch=batch, workers=workers, save_dir=save_path)

    def predict(self, image_path: str, device=0, conf=0.025, save_path = "runs/detect/predict_signature"):

        save_path = os.path.join(save_path, os.path.splitext(os.path.basename(image_path))[0])
        results = self.model.predict(source=image_path, device=device, conf=conf, save_crop=True, save_dir=save_path)
        return save_path
    
class SignatureExtractor:
    @staticmethod
    def isolate_signature(input_path: str, output_path: str):
        os.makedirs(output_path, exist_ok=True)
        crop_dir = os.path.join(input_path, r"crops\signature")

        for filename in os.listdir(crop_dir):
            if filename.lower().endswith((".png", ".jpg", ".jpeg")):
                img_path = os.path.join(crop_dir, filename)
                name_without_ext = os.path.splitext(os.path.basename(filename))[0]
                out_filename = name_without_ext + ".png"
                out_filepath = os.path.join(output_path, out_filename)

                # Load original colored image
                img = cv2.imread(img_path)
                if img is None:
                    print(f"⚠️ Failed to load: {filename}")
                    continue

                # Convert to grayscale
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

                # Invert - so paper becomes black, ink becomes white
                inverted = 255 - gray

                # Apply adaptive thresholding to isolate dark ink regions
                # This handles varying lighting across the image
                thresh = cv2.adaptiveThreshold(
                    inverted, 255,
                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                    cv2.THRESH_BINARY_INV,  # invert back - signature stays white
                    11, 2  # block size, C constant
                )

                # Morphological cleanup to remove noise/holes in signature
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                cleaned = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
                cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel)

                # Create clean signature image (white on transparent/black bg)
                result = cleaned

                # Save result
                cv2.imwrite(out_filepath, result)
                print(f"✅ Extracted: {filename} → {out_filename}")

import imagehash
from PIL import Image

class SignatureHasher:
    @staticmethod
    def compute_hash(image_path, hash_size=8):
        """Compute pHash of signature image"""
        img = Image.open(image_path).convert('L')  # grayscale
        return str(imagehash.phash(img, hash_size=hash_size))  # return as string
    
    @staticmethod
    def compute_dhash(image_path, hash_size=8):
        """Compute dHash - faster, more sensitive to small changes"""
        img = Image.open(image_path).convert('L')
        return str(imagehash.dhash(img, hash_size=hash_size))
    
    @staticmethod
    def compute_ahash(image_path, hash_size=8):
        """Compute average hash"""
        img = Image.open(image_path).convert('L')
        return str(imagehash.average_hash(img, hash_size=hash_size))

import json
import os
from typing import List, Dict, Tuple, Optional

class SignatureRegistry:
    def __init__(self, registry_path: str = "signature_registry.json"):
        self.registry_path = registry_path
        self.signatures = self._load_registry()
    
    def _load_registry(self) -> Dict:
        if os.path.exists(self.registry_path):
            with open(self.registry_path, 'r') as f:
                return json.load(f)
        return {"signatures": []}
    
    def _save_registry(self):
        with open(self.registry_path, 'w') as f:
            json.dump(self.signatures, f, indent=2)
    
    def add(self, label: str, image_path: str, hash_value: str):
        """Add signature to registry"""
        entry = {
            "label": label,
            "image_path": image_path,
            "hash": hash_value,
            "added_date": str(datetime.now())
        }
        self.signatures["signatures"].append(entry)
        self._save_registry()
    
    def remove(self, label: str):
        """Remove all signatures for a label"""
        self.signatures["signatures"] = [
            s for s in self.signatures["signatures"] 
            if s["label"] != label
        ]
        self._save_registry()
    
    def find_similar(self, query_hash: str, threshold: int = 5) -> List[Dict]:
        """Find signatures within Hamming distance threshold"""
        matches = []
        for sig in self.signatures["signatures"]:
            distance = self._hamming_distance(query_hash, sig["hash"])
            if distance <= threshold:
                matches.append({
                    **sig,
                    "distance": distance,
                    "similarity": round((1 - distance / (len(query_hash) * 4)) * 100, 2)
                })
        # Sort by closest match first
        return sorted(matches, key=lambda x: x["distance"])
    
    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        """Calculate Hamming distance between two hashes"""
        if len(hash1) != len(hash2):
            return float('inf')
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))
    
    def identify(self, query_hash: str, threshold: int = 5) -> Optional[Dict]:
        """Identify the best match for a query hash"""
        matches = self.find_similar(query_hash, threshold)
        return matches[0] if matches else None
    
    def verify(self, query_hash: str, expected_label: str, threshold: int = 5) -> bool:
        """Verify if a signature matches expected label (for fraud detection)"""
        matches = self.find_similar(query_hash, threshold)
        return any(m["label"] == expected_label for m in matches)

def register_signatures(labeled_images: Dict[str, List[str]], yolo_model, extractor, registry):
    """
    labeled_images: {"Person_A": ["path/img1.jpg", "path/img2.jpg"], ...}
    """
    results = []
    
    for label, image_paths in labeled_images.items():
        for img_path in image_paths:
            # Step 1: YOLO crop signature
            save_path = yolo_model.predict(img_path)
            
            # Step 2: Extract isolate signature
            crop_dir = os.path.join(save_path, "crops", "signature")
            if not os.path.exists(crop_dir):
                print(f"⚠️ No signature found in {img_path}")
                continue
            
            # Get the cropped signature
            cropped_files = os.listdir(crop_dir)
            if not cropped_files:
                continue
            
            cropped_path = os.path.join(crop_dir, cropped_files[0])
            
            # Save to temp for hashing
            temp_output = "temp_signature.png"
            extractor.isolate_signature(save_path, "temp_dir", temp_output)
            
            # Step 3: Compute hash
            hash_value = SignatureHasher.compute_hash(temp_output)
            
            # Step 4: Add to registry
            registry.add(label, cropped_path, hash_value)
            
            results.append({"label": label, "hash": hash_value})
            
            # Cleanup
            if os.path.exists("temp_dir"):
                shutil.rmtree("temp_dir")
    
    return results

def identify_signature(input_image: str, yolo_model, extractor, registry, threshold: int = 5) -> Dict:
    """
    Identify who signed the document
    Returns: {label, distance, similarity} or {error}
    """
    # Steps 1-3 same as registration
    save_path = yolo_model.predict(input_image)
    extractor.isolate_signature(save_path, "temp_dir")
    temp_path = os.path.join("temp_dir", "signature.png")  # adjust based on actual output
    
    query_hash = SignatureHasher.compute_hash(temp_path)
    
    # Step 4: Find match
    best_match = registry.identify(query_hash, threshold)
    
    # Cleanup
    if os.path.exists("temp_dir"):
        shutil.rmtree("temp_dir")
    
    return best_match if best_match else {"error": "No matching signature found"}

def detect_fraud(input_image: str, expected_signer: str, yolo_model, extractor, registry, threshold: int = 5) -> Dict:
    """
    Check if document was signed by expected person
    Returns: {is_valid: bool, match_details} or {is_valid: False, reason}
    """
    # Get signature and hash it
    save_path = yolo_model.predict(input_image)
    extractor.isolate_signature(save_path, "temp_dir")
    temp_path = os.path.join("temp_dir", "signature.png")
    
    query_hash = SignatureHasher.compute_hash(temp_path)
    
    # Check if it matches expected signer
    is_valid = registry.verify(query_hash, expected_signer, threshold)
    
    if not is_valid:
        # Check if it matches ANYONE else (potential forgery)
        matches = registry.find_similar(query_hash, threshold)
        if matches:
            return {
                "is_valid": False,
                "reason": "Signature belongs to different person",
                "matched_label": matches[0]["label"],
                "confidence": matches[0]["similarity"]
            }
        else:
            return {
                "is_valid": False,
                "reason": "Signature not found in registry (unknown signer)"
            }
    
    return {
        "is_valid": True,
        "signer": expected_signer,
        "confidence": 100  # could calculate actual similarity
    }

if __name__ == "__main__":
    # model = YOLO11n("yolo11n.pt")
    # model.train(train_data_path=r"E:\Coding\SkillStack\ml\CampusCred\data\signature\signature.yaml", epochs=150, save_path=r"E:\Coding\SkillStack\ml\CampusCred\models\yolo\train")

    model = YOLO11n(r"E:\Coding\SkillStack\ml\runs\detect\train6\weights\best.pt")
    save_path = model.predict(r"C:\Users\logan\Downloads\WhatsApp Image 2026-03-23 at 21.30.17.jpeg")
    print(save_path)
    
    extractor = SignatureExtractor()
    extractor.isolate_signature(
        input_path=save_path,
        output_path=r"E:\Coding\SkillStack\ml\CampusCred\runs\detect\predict_signature\extracted"
    )