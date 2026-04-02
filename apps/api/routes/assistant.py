"""Assistant shell API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from packages.shared.assistant_context import AssistantContext, Methodology, WorkflowStage
from packages.shared.assistant_shell import (
    build_context_chips,
    compute_context_hash,
    get_panel_state,
)
from packages.shared.interaction_patterns import Screen

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/panel-state")
def panel_state(ctx: AssistantContext, screen: str) -> dict:
    """Return the full panel state for a screen given the current context."""
    try:
        screen_enum = Screen(screen)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown screen: {screen}")
    state = get_panel_state(ctx, screen_enum)
    return state.model_dump()


@router.post("/context-chips")
def context_chips(ctx: AssistantContext) -> dict:
    """Return context chips for the current context."""
    chips = build_context_chips(ctx)
    return {"chips": [c.model_dump() for c in chips]}


@router.post("/context-hash")
def context_hash(ctx: AssistantContext) -> dict:
    """Return the context hash for logging/audit."""
    return {"context_hash": compute_context_hash(ctx)}
