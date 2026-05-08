from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.schemas.common import ApiResponse, success_response

router = APIRouter(prefix="/engine", tags=["film-engine"])


def _ensure_repo_root_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[6]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


@router.get(
    "/demo-plan",
    response_model=ApiResponse[dict[str, Any]],
    summary="AI Film Engine closed-loop demo plan",
)
async def get_film_engine_demo_plan() -> ApiResponse[dict[str, Any]]:
    """Return a deterministic industrial closed-loop production plan."""
    _ensure_repo_root_on_path()
    from src.film_engine.demo import build_demo_plan_summary

    return success_response(build_demo_plan_summary())


@router.get(
    "/stage-index",
    response_model=ApiResponse[dict[str, Any]],
    summary="AI Film Engine nine-stage progress index",
)
async def get_film_engine_stage_index() -> ApiResponse[dict[str, Any]]:
    """Return resumable stage status for the demo production plan."""
    _ensure_repo_root_on_path()
    from src.film_engine.demo import build_demo_plan_summary
    from src.film_engine.studio import build_stage_index

    summary = build_demo_plan_summary()
    return success_response(
        {
            "project": summary["project"],
            "chapter": summary["chapter"],
            "stages": [stage.__dict__ for stage in build_stage_index(summary)],
        }
    )

