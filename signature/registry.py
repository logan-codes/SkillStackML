import json
import os
from typing import List, Dict, Tuple, Optional
from datetime import datetime

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
