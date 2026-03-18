from pydantic import BaseModel
from typing import Optional
from fastapi import Form, UploadFile, File

class VerifyRequest:
    def __init__(
        self,
        name: str | None = Form(None),
        course_name: str | None = Form(None),
        course_provider: str | None = Form(None),
        date_of_completion: str | None = Form(None),
        file: UploadFile = File(...),
        verification_url: str | None = Form(None),
    ):
        self.name = name 
        self.course_name = course_name
        self.course_provider = course_provider
        self.date_of_completion = date_of_completion
        self.file = file
        self.verification_url = verification_url