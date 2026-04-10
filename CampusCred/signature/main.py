from .pipeline import SignaturePipeline
from .detection import YOLO11n, SignatureExtractor
from .registry import SignatureRegistry
from .hasher import SignatureHasher

yolo= YOLO11n()
extractor = SignatureExtractor()
registry = SignatureRegistry()



sp= SignaturePipeline()
## Register signatures
registry_out = sp.register_signatures({},yolo, extractor, registry)
print(registry_out)

# Identify and detect fraud
input_image= ""
signer= sp.identify_signature(input_image=input_image,yolo_model=yolo, extractor=extractor, registry=registry)
fraud_check = sp.detect_fraud(input_image=input_image,expected_signer= signer["label"], yolo_model=yolo, extractor=extractor, registry=registry)
print(signer)
print(fraud_check)