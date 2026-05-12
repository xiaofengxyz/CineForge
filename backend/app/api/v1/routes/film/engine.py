from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db
from app.core.contracts.video_generation import VideoRatio
from app.schemas.common import ApiResponse, created_response, success_response
from app.services.film.engine_state import (
    FilmEngineConfig,
    FilmEngineConfigUpdate,
    build_project_film_engine_summary,
    build_project_film_engine_series_index,
    create_film_engine_retry_task,
    evaluate_shot_visual_qa,
    get_project_film_engine_config,
    update_project_film_engine_config,
)

router = APIRouter(prefix="/engine", tags=["film-engine"])


class FilmEngineShotQARequest(BaseModel):
    """Request body for manually evaluating one generated shot video."""

    shot_id: str = Field(..., description="镜头 ID")


class FilmEngineRetryTaskRequest(BaseModel):
    """Request body for creating a real retry video task from Film Engine QA."""

    project_id: str = Field(..., description="项目 ID")
    shot_id: str = Field(..., description="镜头 ID")
    chapter_id: str | None = Field(None, description="章节 ID；为空时使用项目第一章")
    ratio: VideoRatio | None = Field(None, description="视频比例；为空时继承镜头/项目默认值")


class FilmEngineTextToDramaPlanRequest(BaseModel):
    """Request body for the text-to-novel-to-drama operating plan."""

    source_text: str = Field(..., description="用户输入的一段故事文字")
    title: str = Field("CineForge Auto Drama", description="自动生成小说/漫剧项目标题")
    config: dict[str, Any] = Field(default_factory=dict, description="阶段开关、模型 endpoint 与运行参数")


def _ensure_repo_root_on_path() -> None:
    """Add repository root to sys.path for root-level Film Engine modules."""
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
async def get_film_engine_stage_index(
    project_id: str | None = Query(None, description="项目 ID；为空时返回内置九阶段验收样例"),
    chapter_id: str | None = Query(None, description="章节 ID；为空时选取项目第一章"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """Return resumable stage status for demo or a Jellyfish project/chapter."""
    _ensure_repo_root_on_path()
    from src.film_engine.demo import build_demo_plan_summary
    from src.film_engine.studio import build_production_workflow_stage_index, build_stage_index

    summary = (
        await build_project_film_engine_summary(db, project_id=project_id, chapter_id=chapter_id)
        if project_id
        else build_demo_plan_summary()
    )
    stages = build_stage_index(summary)
    return success_response(
        {
            "project": summary["project"],
            "chapter": summary["chapter"],
            "all_stages_done": all(stage.status == "done" for stage in stages),
            "summary": summary,
            "workflow_stages": [
                stage.__dict__ for stage in build_production_workflow_stage_index(summary)
            ],
            "stages": [stage.__dict__ for stage in stages],
        }
    )


@router.get(
    "/series-index",
    response_model=ApiResponse[dict[str, Any]],
    summary="AI Film Engine multi-episode production index",
)
async def get_film_engine_series_index(
    project_id: str = Query(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """Return chapter-by-chapter Film Engine status for multi-episode production."""
    _ensure_repo_root_on_path()
    return success_response(await build_project_film_engine_series_index(db, project_id=project_id))


@router.post(
    "/text-to-drama-plan",
    response_model=ApiResponse[dict[str, Any]],
    summary="从一段文字生成小说到漫剧的可执行生产计划",
)
async def create_text_to_drama_plan(
    body: FilmEngineTextToDramaPlanRequest,
) -> ApiResponse[dict[str, Any]]:
    """Run the offline-safe text-to-drama Film Engine workflow."""
    _ensure_repo_root_on_path()
    from src.film_engine.text_to_drama import TextToDramaConfig, TextToDramaPipeline

    config_payload = dict(body.config)
    config_payload.setdefault("title", body.title)
    result = TextToDramaPipeline().run(
        body.source_text,
        config=TextToDramaConfig.from_mapping(config_payload),
    )
    return success_response(result)


@router.get(
    "/config",
    response_model=ApiResponse[FilmEngineConfig],
    summary="获取项目 Film Engine 配置",
)
async def get_film_engine_config(
    project_id: str = Query(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[FilmEngineConfig]:
    """Return project-level Film Engine runtime/QA/retry configuration."""
    return success_response(await get_project_film_engine_config(db, project_id=project_id))


@router.patch(
    "/config",
    response_model=ApiResponse[FilmEngineConfig],
    summary="更新项目 Film Engine 配置",
)
async def update_film_engine_config(
    body: FilmEngineConfigUpdate,
    project_id: str = Query(..., description="项目 ID"),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[FilmEngineConfig]:
    """Persist project-level Film Engine configuration in Project.stats."""
    config = await update_project_film_engine_config(db, project_id=project_id, update=body)
    await db.commit()
    return success_response(config)


@router.post(
    "/qa/evaluate-shot",
    response_model=ApiResponse[dict[str, Any]],
    summary="用 Film Visual QA 重评估单个已生成镜头",
)
async def evaluate_film_engine_shot_qa(
    body: FilmEngineShotQARequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """Run OpenCV, InsightFace, and CLIP visual QA for an existing generated shot video."""
    result = await evaluate_shot_visual_qa(db, shot_id=body.shot_id)
    await db.commit()
    return success_response(result)


@router.post(
    "/retry-task",
    response_model=ApiResponse[dict[str, Any]],
    status_code=201,
    summary="从 Film Engine Retry 请求创建真实视频任务",
)
async def create_film_engine_retry_video_task(
    body: FilmEngineRetryTaskRequest,
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    """Create a video_generation task from the current Film Engine retry request."""
    result = await create_film_engine_retry_task(
        db,
        project_id=body.project_id,
        chapter_id=body.chapter_id,
        shot_id=body.shot_id,
        ratio=body.ratio,
    )
    return created_response(result)
