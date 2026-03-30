from ultralytics import YOLO
from multiprocessing import freeze_support
import cv2
import torch
import torchvision.models as models
import torchvision.transforms as T
from PIL import Image

MODEL_PATH = r"E:\Coding\SkillStack\ml\CampusCred\models\yolo\yolo11n.pt"


def preprocess(img_path):
    img = cv2.imread(img_path, 0)  # grayscale
    img = cv2.resize(img, (224, 224))
    _, img = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    return img

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
        results = self.model.predict(source=image_path, device=device, conf=conf, save_crop=True, save_dir=save_path)


if __name__ == "__main__":
    model = YOLO11n("yolo11n.pt")
    model.train(train_data_path=r"E:\Coding\SkillStack\ml\CampusCred\data\signature\signature.yaml", epochs=150, save_path=r"E:\Coding\SkillStack\ml\CampusCred\models\yolo\train")

    # model = YOLO11n(r"E:\Coding\SkillStack\ml\runs\detect\train6\weights\best.pt")
    # model.predict(r"C:\Users\logan\Downloads\WhatsApp Image 2026-03-23 at 21.30.17.jpeg")