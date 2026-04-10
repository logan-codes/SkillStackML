from ultralytics import YOLO
from multiprocessing import freeze_support
import cv2
import os

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
