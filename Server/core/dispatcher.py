from core.registry import get_workflow, supported_providers
from core import fallback

def dispatch(payload: dict) -> dict:
    provider = payload.get("provider")

    if not provider:
        return {"status": "error", "message": "Payload missing 'provider' field"}

    validate_fn, process_fn = get_workflow(provider)

    # Route to specific workflow if supported, else fallback
    if validate_fn is None:
        print(f"[Dispatcher] '{provider}' not in supported list {supported_providers()} → using fallback")
        validate_fn = fallback.validate
        process_fn  = fallback.process

    # Run validation first
    is_valid, error = validate_fn(payload)
    if not is_valid:
        return {
            "status": "rejected",
            "provider": provider,
            "reason": error
        }

    # Run the workflow
    return process_fn(payload)