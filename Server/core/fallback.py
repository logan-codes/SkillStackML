
def validate(payload: dict) -> tuple[bool, str]:
    """Minimal validation — just needs provider and domain."""
    if "provider" not in payload:
        return False, "Missing 'provider' field"
    if "domain" not in payload:
        return False, "Missing 'domain' field"
    return True, ""

def process(payload: dict) -> dict:
    """Basic approval — no provider-specific API calls."""
    print(f"[Fallback] Basic approval for provider: {payload['provider']}")
    return {
        "status": "approved",
        "provider": payload["provider"],
        "note": "Processed via generalized workflow — no specific integration available",
        "payload": payload
    }