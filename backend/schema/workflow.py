"""
schema/workflow.py
──────────────────
Abstract base class that every platform workflow must inherit from.

Every subclass must implement:
    process(payload: dict) -> dict

And call super().__init__(provider, name, required_fields) so the
registry can auto-validate payloads before routing.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple


class Workflow(ABC):
    """Base workflow — all platform workflows extend this."""

    def __init__(self, provider: str, name: str, req_fields: List[str]):
        self.METADATA = {
            "provider":        provider,   # e.g. "nptel"
            "display_name":    name,       # e.g. "NPTEL Workflow"
            "version":         "1.0",
            "required_fields": req_fields, # payload keys that must be present
        }

    # ── Validation ───────────────────────────────────────────
    def validate(self, payload: dict) -> Tuple[bool, str]:
        """
        Check that all required fields are present in the payload.
        Returns (True, "") on success or (False, error_message) on failure.
        """
        for field in self.METADATA["required_fields"]:
            if field not in payload:
                return False, f"Missing required field: '{field}'"
        return True, ""

    # ── Processing ───────────────────────────────────────────
    @abstractmethod
    def process(self, payload: dict) -> dict:
        """
        Core verification logic.  Must be implemented by every subclass.

        Args:
            payload: dict containing at minimum the fields listed in
                     METADATA["required_fields"].

        Returns:
            dict with at minimum:
                {
                    "status":         str,   # "success" | "retry" | "error"
                    "is_genuine":     bool,
                    "message":        str,
                    "field_breakdown": dict,
                    "data":           dict,
                }
        """
        ...
