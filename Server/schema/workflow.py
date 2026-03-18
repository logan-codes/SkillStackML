from typing import List

class Workflow:
    def __init__(self, provider: str, name: str, req_fields:List):
        self.METADATA={
            "provider": provider,
            "display_name":  name,
            "version": "1.0",
            "required_fields": req_fields
        }
    def validate(self, payload: dict) -> tuple[bool,str]:
        for field in self.METADATA["required_fields"]:
            if field not in payload:
                return False, f"Missing required field: '{field}'"
            
        return True, ""
    
    def process(self, *args, **kwargs):
        pass