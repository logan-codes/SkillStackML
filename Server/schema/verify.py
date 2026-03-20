from fastapi import Form, UploadFile, File

class VerifyRequest:
    def __init__(
        self,
        provider: str = Form(...),
        name: str | None = Form(None),
        course_name: str | None = Form(None),
        date_of_completion: str | None = Form(None),
        file: UploadFile = File(...),
        verification_url: str | None = Form(None),
    ):
        self.provider = provider
        self.name = name 
        self.course_name = course_name
        self.date_of_completion = date_of_completion
        self.file = file
        self.verification_url = verification_url