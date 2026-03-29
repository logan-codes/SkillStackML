from langchain_core.runnables import RunnableLambda
from transformers import AutoProcessor, AutoModelForImageTextToText 
import torch
import os

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")

class GLMOcr:
    def __init__(self):
        self.local_path = os.path.join(MODELS_DIR,"zai-org/GLM-OCR")
        try:
            self.processor = AutoProcessor.from_pretrained(self.local_path)
            self.model = AutoModelForImageTextToText.from_pretrained(
                pretrained_model_name_or_path=self.local_path,
                torch_dtype="auto",
            )
        except:
            self.processor = AutoProcessor.from_pretrained("zai-org/GLM-OCR")
            self.model = AutoModelForImageTextToText.from_pretrained(
                pretrained_model_name_or_path="zai-org/GLM-OCR",
                torch_dtype="auto",
            )
            # self._save()
        if torch.cuda.is_available():
            self.device = "cuda" 
        else:
            self.device="cpu"
        self.model.to(self.device)
        self.model.eval()
        
        if self.device == "cuda":
            self.model = self.model.half()

    def ocr_glm(self,image_path):
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "url": image_path
                    },
                    {
                        "type": "text",
                        "text": "Text Recognition:"
                    }
                ],
            }
        ]
        inputs = self.processor.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt"
        ).to(self.device)
        inputs.pop("token_type_ids", None)
        
        with torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=8192)
        
        output_text = self.processor.decode(generated_ids[0][inputs["input_ids"].shape[1]:], skip_special_tokens=False)
        print(output_text)

        return output_text
    
    def _save(self):
        self.processor.save_pretrained(self.local_path)
        self.model.save_pretrained(self.local_path)

glm=GLMOcr()
print(glm.device)
ocr_chain = RunnableLambda(glm.ocr_glm)

result = ocr_chain.invoke(r"C:\Users\logan\Downloads\WhatsApp Image 2026-03-26 at 13.37.09.jpeg")
print(result)