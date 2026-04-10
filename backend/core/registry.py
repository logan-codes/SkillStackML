"""
core/registry.py
────────────────
Workflow Registry — maps platform names to workflow instances.

Adding a new platform:
    1. Create workflows/myplatform.py inheriting from Workflow
    2. Add an entry to WORKFLOW_REGISTRY below — that's it.

Usage:
    from core.registry import get_workflow, list_workflows
    workflow = get_workflow("coursera")
    result   = workflow.process(payload)
"""

from workflows.nptel       import NPTELWorkflow
from workflows.codetantra  import CodeTantraWorkflow
from workflows.coursera    import CourseraWorkflow
from workflows.udemy       import UdemyWorkflow

# ── Registry: provider_name → workflow instance ──────────────
WORKFLOW_REGISTRY: dict = {
    "nptel":       NPTELWorkflow(),
    "codetantra":  CodeTantraWorkflow(),
    "coursera":    CourseraWorkflow(),
    "udemy":       UdemyWorkflow(),
}


def get_workflow(provider: str):
    """
    Return the workflow instance for the given provider name.

    Args:
        provider: Platform key e.g. "nptel", "coursera".

    Raises:
        ValueError: If no workflow is registered for that provider.
    """
    workflow = WORKFLOW_REGISTRY.get(provider.lower())
    if not workflow:
        available = list(WORKFLOW_REGISTRY.keys())
        raise ValueError(
            f"No workflow registered for provider '{provider}'. "
            f"Available: {available}"
        )
    return workflow


def list_workflows() -> dict:
    """Return metadata for all registered workflows."""
    return {name: wf.METADATA for name, wf in WORKFLOW_REGISTRY.items()}
