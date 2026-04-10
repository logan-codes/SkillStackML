from typing import Dict, List
from .hasher import SignatureHasher
from .detection import YOLO11n, SignatureExtractor
from .registry import SignatureRegistry
import os
import shutil

class SignaturePipeline:
    def register_signatures(labeled_images: Dict[str, List[str]], yolo_model: YOLO11n, extractor: SignatureExtractor, registry: SignatureRegistry) -> List[Dict]:
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

    def identify_signature(input_image: str, yolo_model: YOLO11n, extractor: SignatureExtractor, registry: SignatureRegistry, threshold: int = 5) -> Dict:
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

    def detect_fraud(input_image: str, expected_signer: str, yolo_model: YOLO11n, extractor: SignatureExtractor, registry: SignatureRegistry, threshold: int = 5) -> Dict:
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
