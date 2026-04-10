from PIL import Image
import imagehash

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
