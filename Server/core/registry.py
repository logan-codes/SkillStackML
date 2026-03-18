from core.logger import get_logger

import importlib
import pkgutil
import json
import os

logger=get_logger(__name__)

REGISTRY_FILE = "registry.json"
WORKFLOWS_PKG = "workflows"

def discover_and_sync() -> dict:
    """Scan workflows/ folder and rebuild registry.json"""
    registry = {}

    package = importlib.import_module(WORKFLOWS_PKG)
    for _, module_name, _ in pkgutil.iter_modules(package.__path__ ):
        logger.info(f"Module Names:{module_name}")
        full_name = f"{WORKFLOWS_PKG}.{module_name}"
        module = importlib.import_module(full_name)

        # Only register if it follows the contract
        if hasattr(module, "METADATA") and hasattr(module, "validate") and hasattr(module, "process"):
            meta = module.METADATA
            provider_key = meta["provider"]
            registry[provider_key] = {
                "module": full_name,
                "display_name": meta.get("display_name", provider_key),
                "version": meta.get("version", "1.0"),
                "required_fields": meta.get("required_fields", [])
            }
            logger.info(f"Loaded workflow: {provider_key} ({meta.get('display_name')})")

    with open(REGISTRY_FILE, "w") as f:
        json.dump(registry, f, indent=2)

    logger.info(f"Registry updated → {len(registry)} provider(s) supported")
    return registry


def load_registry() -> dict:
    if not os.path.exists(REGISTRY_FILE):
        return discover_and_sync()
    with open(REGISTRY_FILE, "r") as f:
        return json.load(f)


def supported_providers() -> list:
    return list(load_registry().keys())


def get_workflow(provider: str):
    """Return the (validate_fn, process_fn) for a provider, or None if unsupported."""
    registry = load_registry()
    if provider not in registry:
        return None, None
    module = importlib.import_module(registry[provider]["module"])
    return module.validate, module.process