from pydantic import BaseModel
from typing import Optional
from fastapi import Form, UploadFile, File

class VerifyRequest:
    def __init__(
        self,
        file: UploadFile = File(...),
        manual_url: str | None = Form(None),
    ):
        self.file = file
        self.manual_url = manual_url