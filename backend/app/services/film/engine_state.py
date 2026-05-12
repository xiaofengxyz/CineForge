from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.studio import (
    Chapter,
    Character,
    CharacterImage,
    Scene,
    SceneImage,
    Shot,
    ShotCharacterLink,
    ShotDetail,
    ShotDialogLine,
    ShotFrameImage,
    ShotStatus,
    FileItem,
    Project,
)
from app.core.task_manager import DeliveryMode, SqlAlchemyTaskStore, TaskManager
from app.models.task import GenerationDeliveryMode, GenerationTask, GenerationTaskStatus
from app.models.task_links import GenerationTaskLink
from app.services.film.generated_video import build_run_args
from app.services.film.visual_qa import VisualQAEvaluation, evaluate_file_item_with_film_visual_qa
from app.services.common import entity_not_found
from app.services.studio.shot_status import mark_shot_generating
from app.tasks.execute_task import enqueue_task_execution

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.film_engine.core import (
    CharacterBible,
    ClosedLoopProductionPlanner,
    JELLYFISH_FILM_WORKFLOW,
    QAEngine,
    RenderResult,
    SceneBible,
    StudioAsset,
    StudioChapter,
    StudioProject,
    StudioShot,
)

FILM_ENGINE_CONFIG_KEY = "film_engine_config"

ReferenceMode = Literal["first", "last", "key", "first_last", "first_last_key", "text_only"]


class FilmEngineConfig(BaseModel):
    enabled: bool = Field(True, description="是否在项目流程中启用 Film Engine 闭环")
    runtime_provider: str = Field("kling", description="运行时供应商标识")
    runtime_model: str = Field("kling-v1", description="视频运行时模型")
    reference_mode: ReferenceMode = Field("first_last_key", description="默认参考帧策略")
    lens: str = Field("35mm", description="Director DSL 默认镜头焦段")
    output_dir: str = Field("output/renders", description="渲染输出目录")
    qa_threshold: float = Field(0.75, ge=0, le=1, description="QA 参考阈值")
    auto_retry: bool = Field(True, description="QA 未通过时是否自动生成 Retry 请求")
    retry_limit: int = Field(2, ge=0, le=10, description="自动重试上限")


class FilmEngineConfigUpdate(BaseModel):
    enabled: bool | None = None
    runtime_provider: str | None = None
    runtime_model: str | None = None
    reference_mode: ReferenceMode | None = None
    lens: str | None = None
    output_dir: str | None = None
    qa_threshold: float | None = Field(None, ge=0, le=1)
    auto_retry: bool | None = None
    retry_limit: int | None = Field(None, ge=0, le=10)


def _clean_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _coerce_metric_dict(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    supported = set(QAEngine.default_thresholds)
    metrics: dict[str, float] = {}
    for key, raw_score in value.items():
        if str(key) not in supported:
            continue
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        metrics[str(key)] = max(0.0, min(1.0, score))
    return metrics


def _extract_task_qa_metrics(payload: Any) -> dict[str, float]:
    if not isinstance(payload, dict):
        return {}
    for key in ("film_engine_qa_metrics", "qa_metrics", "metrics"):
        metrics = _coerce_metric_dict(payload.get(key))
        if metrics:
            return metrics
    visual_qa = payload.get("film_engine_visual_qa")
    if isinstance(visual_qa, dict):
        metrics = _coerce_metric_dict(visual_qa.get("metrics"))
        if metrics:
            return metrics
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("film_engine_qa_metrics", "qa_metrics", "metrics"):
            metrics = _coerce_metric_dict(metadata.get(key))
            if metrics:
                return metrics
        visual_qa = metadata.get("film_engine_visual_qa")
        if isinstance(visual_qa, dict):
            metrics = _coerce_metric_dict(visual_qa.get("metrics"))
            if metrics:
                return metrics
    return {}


def get_film_engine_config_from_project(project: Project) -> FilmEngineConfig:
    stats = project.stats if isinstance(project.stats, dict) else {}
    raw = stats.get(FILM_ENGINE_CONFIG_KEY)
    if isinstance(raw, dict):
        return FilmEngineConfig.model_validate(raw)
    return FilmEngineConfig()


async def get_project_film_engine_config(
    db: AsyncSession,
    *,
    project_id: str,
) -> FilmEngineConfig:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=entity_not_found("Project"))
    return get_film_engine_config_from_project(project)


async def update_project_film_engine_config(
    db: AsyncSession,
    *,
    project_id: str,
    update: FilmEngineConfigUpdate,
) -> FilmEngineConfig:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=entity_not_found("Project"))

    current = get_film_engine_config_from_project(project)
    update_data = update.model_dump(exclude_unset=True)
    next_config = current.model_copy(update=update_data)
    stats = dict(project.stats or {})
    stats[FILM_ENGINE_CONFIG_KEY] = next_config.model_dump()
    project.stats = stats
    await db.flush()
    await db.refresh(project)
    return next_config


async def _select_chapter(
    db: AsyncSession,
    *,
    project: Project,
    chapter_id: str | None,
) -> Chapter | None:
    if chapter_id:
        chapter = await db.get(Chapter, chapter_id)
        if chapter is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=entity_not_found("Chapter"))
        if chapter.project_id != project.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="chapter_id does not belong to project_id")
        return chapter

    stmt = select(Chapter).where(Chapter.project_id == project.id).order_by(Chapter.index).limit(1)
    return (await db.execute(stmt)).scalars().first()


async def _list_shots(db: AsyncSession, chapter_id: str) -> list[Shot]:
    stmt = select(Shot).where(Shot.chapter_id == chapter_id).order_by(Shot.index)
    return list((await db.execute(stmt)).scalars().all())


async def _details_by_shot(db: AsyncSession, shot_ids: list[str]) -> dict[str, ShotDetail]:
    if not shot_ids:
        return {}
    stmt = select(ShotDetail).where(ShotDetail.id.in_(shot_ids))
    return {row.id: row for row in (await db.execute(stmt)).scalars().all()}


async def _dialogue_by_shot(db: AsyncSession, shot_ids: list[str]) -> dict[str, list[str]]:
    if not shot_ids:
        return {}
    stmt = select(ShotDialogLine).where(ShotDialogLine.shot_detail_id.in_(shot_ids)).order_by(ShotDialogLine.index)
    result: dict[str, list[str]] = {shot_id: [] for shot_id in shot_ids}
    for row in (await db.execute(stmt)).scalars().all():
        if row.text:
            result.setdefault(row.shot_detail_id, []).append(row.text)
    return result


async def _frame_refs_by_shot(db: AsyncSession, shot_ids: list[str]) -> dict[str, list[str]]:
    if not shot_ids:
        return {}
    stmt = select(ShotFrameImage).where(ShotFrameImage.shot_detail_id.in_(shot_ids)).order_by(ShotFrameImage.frame_type)
    result: dict[str, list[str]] = {shot_id: [] for shot_id in shot_ids}
    for row in (await db.execute(stmt)).scalars().all():
        if row.file_id:
            result.setdefault(row.shot_detail_id, []).append(row.file_id)
    return result


async def _character_reference_refs_by_shot(
    db: AsyncSession,
    shot_ids: list[str],
) -> dict[str, dict[str, list[str]]]:
    """Return character reference image file IDs grouped by shot and character."""
    character_ids_by_shot = await _character_ids_by_shot(db, shot_ids)
    character_ids = {
        character_id
        for ids in character_ids_by_shot.values()
        for character_id in ids
        if character_id
    }
    if not character_ids:
        return {shot_id: {} for shot_id in shot_ids}

    stmt = (
        select(CharacterImage)
        .where(CharacterImage.character_id.in_(character_ids))
        .order_by(CharacterImage.is_primary.desc(), CharacterImage.id)
    )
    refs_by_character: dict[str, list[str]] = {character_id: [] for character_id in character_ids}
    for row in (await db.execute(stmt)).scalars().all():
        if row.file_id:
            refs_by_character.setdefault(row.character_id, []).append(row.file_id)

    return {
        shot_id: {
            character_id: refs_by_character.get(character_id, [])
            for character_id in character_ids_by_shot.get(shot_id, [])
            if refs_by_character.get(character_id)
        }
        for shot_id in shot_ids
    }


async def _character_ids_by_shot(db: AsyncSession, shot_ids: list[str]) -> dict[str, list[str]]:
    if not shot_ids:
        return {}
    stmt = select(ShotCharacterLink).where(ShotCharacterLink.shot_id.in_(shot_ids)).order_by(ShotCharacterLink.index)
    result: dict[str, list[str]] = {shot_id: [] for shot_id in shot_ids}
    for row in (await db.execute(stmt)).scalars().all():
        result.setdefault(row.shot_id, []).append(row.character_id)
    return result


async def _task_qa_metrics_by_shot(db: AsyncSession, shot_ids: list[str]) -> dict[str, dict[str, float]]:
    if not shot_ids:
        return {}
    stmt = (
        select(GenerationTaskLink, GenerationTask)
        .join(GenerationTask, GenerationTask.id == GenerationTaskLink.task_id)
        .where(
            GenerationTaskLink.resource_type == "video",
            GenerationTaskLink.relation_type == "video",
            GenerationTaskLink.relation_entity_id.in_(shot_ids),
        )
        .order_by(GenerationTask.updated_at.desc())
    )
    result: dict[str, dict[str, float]] = {}
    for link, task in (await db.execute(stmt)).all():
        shot_id = str(link.relation_entity_id or "")
        if not shot_id or shot_id in result:
            continue
        metrics = _extract_task_qa_metrics(task.result) or _extract_task_qa_metrics(task.payload)
        if metrics:
            result[shot_id] = metrics
    return result


class _CreateOnlyTask:
    """Minimal TaskManager-compatible task used when Film Engine creates records."""

    async def run(self, *args: object, **kwargs: object):  # noqa: ANN001, ANN003
        """No-op task body; Celery resolves the real executor from task_kind."""
        return None

    async def status(self) -> dict[str, object]:
        """Return an empty status because this object is never executed directly."""
        return {}

    async def is_done(self) -> bool:
        """Report unfinished so TaskManager only uses it for record creation."""
        return False

    async def get_result(self) -> object:
        """Return no result because worker execution writes GenerationTask.result."""
        return None


async def _latest_video_task_for_shot(
    db: AsyncSession,
    *,
    shot_id: str,
) -> tuple[GenerationTaskLink | None, GenerationTask | None]:
    """Return the newest video-linked task for a shot, if one exists."""
    stmt = (
        select(GenerationTaskLink, GenerationTask)
        .join(GenerationTask, GenerationTask.id == GenerationTaskLink.task_id)
        .where(
            GenerationTaskLink.resource_type == "video",
            GenerationTaskLink.relation_type == "video",
            GenerationTaskLink.relation_entity_id == shot_id,
        )
        .order_by(GenerationTask.updated_at.desc(), GenerationTask.id.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).first()
    if row is None:
        return None, None
    return row[0], row[1]


def _merge_visual_qa_result(
    *,
    raw_result: Any,
    evaluation: VisualQAEvaluation,
) -> dict[str, Any]:
    """Merge Film Visual QA metrics into a GenerationTask.result payload."""
    result_payload = dict(raw_result) if isinstance(raw_result, dict) else {}
    existing_metrics = _extract_task_qa_metrics(result_payload)
    merged_metrics = {**existing_metrics, **evaluation.metrics}
    result_payload["film_engine_visual_qa"] = evaluation.as_result_payload()
    if merged_metrics:
        result_payload["film_engine_qa_metrics"] = merged_metrics
    return result_payload


def _visual_qa_response_payload(
    *,
    shot_id: str,
    task_id: str,
    evaluation: VisualQAEvaluation,
) -> dict[str, Any]:
    """Build an API response payload for a manual Film Visual QA run."""
    return {
        "shot_id": shot_id,
        "task_id": task_id,
        "evaluator": evaluation.evaluator,
        "status": evaluation.status,
        "metrics": dict(evaluation.metrics),
        "details": dict(evaluation.details),
        "reason": evaluation.reason,
    }


def _extract_prompt_text_from_payload(payload: Any) -> str:
    """Find a compiled video prompt from task payload/result variants."""
    if not isinstance(payload, dict):
        return ""
    containers: list[dict[str, Any]] = [payload]
    for key in ("run_args", "input", "film_engine_qa_context", "prompt_preview"):
        value = payload.get(key)
        if isinstance(value, dict):
            containers.append(value)
    run_args = payload.get("run_args")
    if isinstance(run_args, dict):
        for key in ("input", "film_engine_qa_context", "prompt_preview"):
            value = run_args.get(key)
            if isinstance(value, dict):
                containers.append(value)

    for container in containers:
        for key in ("prompt", "rendered_prompt", "base_prompt"):
            text = _clean_text(container.get(key))
            if text:
                return text
    return ""


async def _fallback_prompt_text_for_shot(db: AsyncSession, *, shot: Shot) -> str:
    """Build a deterministic QA text fallback from shot story fields."""
    detail = await db.get(ShotDetail, shot.id)
    parts = [shot.script_excerpt, shot.title]
    if detail is not None:
        parts.extend([detail.description, " ".join(str(item) for item in (detail.action_beats or []))])
    return " ".join(_clean_text(part) for part in parts if _clean_text(part))


async def evaluate_shot_visual_qa(
    db: AsyncSession,
    *,
    shot_id: str,
) -> dict[str, Any]:
    """Evaluate an existing generated shot video and persist Film Visual QA metrics."""
    shot = await db.get(Shot, shot_id)
    if shot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=entity_not_found("Shot"))
    if not shot.generated_video_file_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shot has no generated video")

    video_file = await db.get(FileItem, shot.generated_video_file_id)
    if video_file is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=entity_not_found("FileItem"))

    link, task = await _latest_video_task_for_shot(db, shot_id=shot_id)
    frame_refs_by_shot = await _frame_refs_by_shot(db, [shot_id])
    character_refs_by_shot = await _character_reference_refs_by_shot(db, [shot_id])
    prompt_text = ""
    if task is not None:
        prompt_text = _extract_prompt_text_from_payload(task.payload) or _extract_prompt_text_from_payload(task.result)
    if not prompt_text:
        prompt_text = await _fallback_prompt_text_for_shot(db, shot=shot)

    evaluation = await evaluate_file_item_with_film_visual_qa(
        db,
        video_file=video_file,
        reference_file_ids=frame_refs_by_shot.get(shot_id, []),
        character_reference_file_ids_by_id=character_refs_by_shot.get(shot_id, {}),
        prompt_text=prompt_text,
    )
    if task is not None:
        task.result = _merge_visual_qa_result(raw_result=task.result, evaluation=evaluation)
        await db.flush()
        return _visual_qa_response_payload(shot_id=shot_id, task_id=task.id, evaluation=evaluation)

    task_id = f"film-qa-{uuid.uuid4().hex}"
    task = GenerationTask(
        id=task_id,
        mode=GenerationDeliveryMode.async_polling,
        task_kind="film_visual_qa",
        status=GenerationTaskStatus.succeeded,
        progress=100,
        payload={"run_args": {"shot_id": shot_id, "evaluator": evaluation.evaluator}},
        result=_merge_visual_qa_result(raw_result={"file_id": video_file.id}, evaluation=evaluation),
        error="",
    )
    db.add(task)
    db.add(
        GenerationTaskLink(
            task_id=task.id,
            resource_type="video",
            relation_type="video",
            relation_entity_id=shot_id,
            file_id=video_file.id,
            status=(link.status if link is not None else None) or "todo",
        )
    )
    await db.flush()
    return _visual_qa_response_payload(shot_id=shot_id, task_id=task.id, evaluation=evaluation)


def _find_retry_request(summary: dict[str, Any], *, shot_id: str) -> dict[str, Any] | None:
    """Find the Film Engine retry request for a specific shot."""
    for item in summary.get("retry_requests") or []:
        if isinstance(item, dict) and item.get("shot_id") == shot_id:
            return item
    return None


def _resolve_retry_ratio(
    *,
    project: Project,
    detail: ShotDetail | None,
    requested_ratio: str | None,
) -> str:
    """Resolve the ratio used by Film Engine retry video tasks."""
    if requested_ratio:
        return requested_ratio
    if detail is not None and detail.override_video_ratio:
        return detail.override_video_ratio
    if project.default_video_ratio:
        return project.default_video_ratio
    return "16:9"


async def create_film_engine_retry_task(
    db: AsyncSession,
    *,
    project_id: str,
    shot_id: str,
    chapter_id: str | None = None,
    ratio: str | None = None,
) -> dict[str, Any]:
    """Create a real video_generation task from a Film Engine retry request."""
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=entity_not_found("Project"))
    chapter = await _select_chapter(db, project=project, chapter_id=chapter_id)
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Project has no chapter")

    shot = await db.get(Shot, shot_id)
    if shot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=entity_not_found("Shot"))
    if shot.chapter_id != chapter.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="shot_id does not belong to chapter_id")

    summary = await build_project_film_engine_summary(db, project_id=project.id, chapter_id=chapter.id)
    retry_request = _find_retry_request(summary, shot_id=shot_id)
    if retry_request is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shot has no Film Engine retry request")

    config = get_film_engine_config_from_project(project)
    detail = await db.get(ShotDetail, shot_id)
    frame_refs_by_shot = await _frame_refs_by_shot(db, [shot_id])
    resolved_ratio = _resolve_retry_ratio(
        project=project,
        detail=detail,
        requested_ratio=ratio,
    )
    run_args = await build_run_args(
        db,
        shot_id=shot_id,
        reference_mode=config.reference_mode,
        prompt=str(retry_request.get("prompt") or ""),
        images=frame_refs_by_shot.get(shot_id, []),
        ratio=resolved_ratio,
    )
    run_args["film_engine_retry"] = {
        "project_id": project.id,
        "chapter_id": chapter.id,
        "shot_id": shot_id,
        "reason_codes": list(retry_request.get("reason_codes") or []),
        "parameters": dict(retry_request.get("parameters") or {}),
    }

    store = SqlAlchemyTaskStore(db)
    task_manager = TaskManager(store=store, strategies={})
    task_record = await task_manager.create(
        task=_CreateOnlyTask(),
        mode=DeliveryMode.async_polling,
        task_kind="video_generation",
        run_args=run_args,
    )
    db.add(
        GenerationTaskLink(
            task_id=task_record.id,
            resource_type="video",
            relation_type="video",
            relation_entity_id=shot_id,
        )
    )
    await mark_shot_generating(db, shot_id=shot_id)
    # The worker opens a separate DB session, so commit before dispatching.
    await db.commit()
    enqueue_task_execution(task_record.id)
    return {
        "task_id": task_record.id,
        "shot_id": shot_id,
        "chapter_id": chapter.id,
        "ratio": resolved_ratio,
        "reason_codes": list(retry_request.get("reason_codes") or []),
        "retry_prompt": str(retry_request.get("prompt") or ""),
    }


async def _character_bibles_and_assets(
    db: AsyncSession,
    *,
    character_ids: set[str],
) -> tuple[list[CharacterBible], list[StudioAsset]]:
    if not character_ids:
        return [], []

    characters = list((await db.execute(select(Character).where(Character.id.in_(character_ids)))).scalars().all())
    image_rows = list((await db.execute(select(CharacterImage).where(CharacterImage.character_id.in_(character_ids)))).scalars().all())
    refs_by_character: dict[str, list[str]] = {character_id: [] for character_id in character_ids}
    for row in image_rows:
        if row.file_id:
            refs_by_character.setdefault(row.character_id, []).append(row.file_id)

    bibles: list[CharacterBible] = []
    assets: list[StudioAsset] = []
    for character in characters:
        refs = refs_by_character.get(character.id, [])
        bibles.append(
            CharacterBible(
                id=character.id,
                name=character.name,
                reference_media=refs,
                default_outfit=character.costume_id,
                outfits={character.costume_id: character.costume_id} if character.costume_id else {},
                negative_terms=[f"wrong {character.name}", "identity drift"],
                identity_terms=[character.name],
            )
        )
        assets.append(
            StudioAsset(
                id=character.id,
                kind="character",
                name=character.name,
                description=character.description,
                reference_media=refs,
            )
        )
    return bibles, assets


async def _scene_bibles_and_assets(
    db: AsyncSession,
    *,
    scene_ids: set[str],
    fallback_mood_by_scene: dict[str, str],
) -> tuple[list[SceneBible], list[StudioAsset]]:
    if not scene_ids:
        return [], []

    scenes = list((await db.execute(select(Scene).where(Scene.id.in_(scene_ids)))).scalars().all())
    image_rows = list((await db.execute(select(SceneImage).where(SceneImage.scene_id.in_(scene_ids)))).scalars().all())
    refs_by_scene: dict[str, list[str]] = {scene_id: [] for scene_id in scene_ids}
    for row in image_rows:
        if row.file_id:
            refs_by_scene.setdefault(row.scene_id, []).append(row.file_id)

    bibles: list[SceneBible] = []
    assets: list[StudioAsset] = []
    for scene in scenes:
        refs = refs_by_scene.get(scene.id, [])
        tags = [str(item) for item in (scene.tags or []) if str(item).strip()]
        lighting = tags[0] if tags else "continuity_key_light"
        mood = fallback_mood_by_scene.get(scene.id) or (tags[1] if len(tags) > 1 else "cinematic")
        bibles.append(
            SceneBible(
                id=scene.id,
                name=scene.name,
                lighting=lighting,
                mood=mood,
                reference_media=refs,
            )
        )
        assets.append(
            StudioAsset(
                id=scene.id,
                kind="scene",
                name=scene.name,
                description=scene.description,
                reference_media=refs,
                metadata={"lighting": lighting, "mood": mood},
            )
        )
    return bibles, assets


def _estimate_generated_shot_qa_metrics(
    *,
    shot: StudioShot,
    character_bibles_by_id: dict[str, CharacterBible],
    scene_bibles_by_id: dict[str, SceneBible],
) -> dict[str, float]:
    """Build deterministic proxy QA metrics until CV model metrics are attached to tasks."""

    metrics: dict[str, float] = {}
    if shot.character_ids:
        characters = [character_bibles_by_id.get(character_id) for character_id in shot.character_ids]
        known_characters = [item for item in characters if item is not None]
        has_identity_refs = bool(known_characters) and all(item.reference_media for item in known_characters)
        has_any_outfit = any(item.resolve_outfit() for item in known_characters)
        has_outfit_lock = has_any_outfit and all(item.resolve_outfit() for item in known_characters)
        metrics["face_similarity"] = 0.92 if has_identity_refs else 0.68
        if has_any_outfit:
            metrics["outfit_similarity"] = 0.90 if has_outfit_lock else 0.72

    if shot.scene_id:
        scene = scene_bibles_by_id.get(shot.scene_id)
        has_scene_lock = bool(scene and (scene.reference_media or scene.lighting or scene.mood))
        metrics["lighting_similarity"] = 0.90 if has_scene_lock else 0.66

    has_action = bool(_clean_text(shot.summary) and shot.duration and shot.duration > 0)
    metrics["clip_score"] = 0.88 if has_action else 0.50
    return metrics


def _empty_summary(
    *,
    project: Project,
    chapter: Chapter | None,
    config: FilmEngineConfig,
) -> dict[str, Any]:
    chapter_payload = {"id": chapter.id, "title": chapter.title} if chapter else {"id": "", "title": "未选择章节"}
    return {
        "project": {"id": project.id, "title": project.name},
        "chapter": chapter_payload,
        "workflow": list(JELLYFISH_FILM_WORKFLOW),
        "metadata": {
            "mode": "jellyfish_project_context",
            "scope": "project",
            "shot_count": 0,
            "plannable_shot_count": 0,
            "ready_shot_count": 0,
            "generated_video_count": 0,
            "config": config.model_dump(),
            "next_action": {
                "key": "create_chapter" if chapter is None else "extract_shots",
                "label": "创建章节" if chapter is None else "提取分镜",
                "hint": "先创建章节，再进入 Film Engine 闭环。" if chapter is None else "当前章节还没有可规划分镜。",
            },
            "workflow_status": {},
        },
        "render_requests": [],
        "qa": {"passed": False, "reports": []},
        "retry_requests": [],
        "post_production": {"enabled": False, "output_path": None},
    }


def _workflow_status(
    *,
    chapter: Chapter,
    total_shots: int,
    plannable_shots: int,
    ready_shots: int,
    linked_character_count: int,
    linked_scene_count: int,
    render_request_count: int,
    qa_report_count: int,
    retry_count: int,
    generated_video_count: int,
) -> dict[str, dict[str, Any]]:
    has_script = bool(_clean_text(chapter.condensed_text) or _clean_text(chapter.raw_text) or total_shots)
    shot_prepared = total_shots > 0 and ready_shots == total_shots
    has_assets = linked_character_count > 0 or linked_scene_count > 0
    return {
        "script_breakdown": {
            "done": has_script,
            "evidence": "章节文本或分镜已进入结构化流程。" if has_script else "章节原文为空，尚未进入拆解。",
            "metrics": {"has_script": has_script, "shot_count": total_shots},
        },
        "shot_preparation": {
            "done": shot_prepared,
            "evidence": f"Ready shots={ready_shots}/{total_shots}.",
            "metrics": {"ready_shots": ready_shots, "total_shots": total_shots},
        },
        "asset_consistency": {
            "done": has_assets,
            "evidence": f"Linked characters={linked_character_count}, scenes={linked_scene_count}.",
            "metrics": {"linked_characters": linked_character_count, "linked_scenes": linked_scene_count},
        },
        "film_state": {
            "done": plannable_shots > 0,
            "evidence": f"Continuity-ready shots={plannable_shots}.",
            "metrics": {"plannable_shots": plannable_shots},
        },
        "prompt_compiler": {
            "done": render_request_count > 0,
            "evidence": f"Compiled render requests={render_request_count}.",
            "metrics": {"render_requests": render_request_count},
        },
        "runtime_adapter": {
            "done": render_request_count > 0,
            "evidence": f"Provider-neutral requests={render_request_count}.",
            "metrics": {"render_requests": render_request_count},
        },
        "qa_engine": {
            "done": qa_report_count > 0,
            "evidence": f"QA reports={qa_report_count}.",
            "metrics": {"qa_reports": qa_report_count},
        },
        "retry_engine": {
            "done": qa_report_count > 0,
            "evidence": f"Retry requests={retry_count}.",
            "metrics": {"retry_requests": retry_count},
        },
        "final_export": {
            "done": plannable_shots > 0 and generated_video_count >= plannable_shots,
            "evidence": f"Generated videos={generated_video_count}/{plannable_shots}.",
            "metrics": {"generated_videos": generated_video_count, "plannable_shots": plannable_shots},
        },
    }


def _next_action(
    *,
    total_shots: int,
    plannable_shots: int,
    ready_shots: int,
    render_request_count: int,
    generated_video_count: int,
) -> dict[str, str]:
    if total_shots == 0:
        return {"key": "extract_shots", "label": "提取分镜", "hint": "先把章节文本拆成镜头，Film Engine 才有图工作流。"}
    if ready_shots < total_shots:
        return {"key": "prepare_shots", "label": "准备镜头", "hint": "补齐镜头时长、画面、角色/场景和参考帧。"}
    if render_request_count == 0:
        return {"key": "compile_prompts", "label": "检查提示词", "hint": "镜头已就绪，但还没有可运行的渲染请求。"}
    if generated_video_count < plannable_shots:
        return {"key": "generate_video", "label": "生成视频", "hint": "Film Engine 已编译运行计划，可进入分镜工作室生成视频。"}
    return {"key": "final_export", "label": "进入剪辑", "hint": "当前章节已有生成结果，可进入后期剪辑。"}


async def build_project_film_engine_summary(
    db: AsyncSession,
    *,
    project_id: str,
    chapter_id: str | None = None,
) -> dict[str, Any]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=entity_not_found("Project"))

    config = get_film_engine_config_from_project(project)
    chapter = await _select_chapter(db, project=project, chapter_id=chapter_id)
    if chapter is None:
        return _empty_summary(project=project, chapter=None, config=config)

    shots = await _list_shots(db, chapter.id)
    if not shots:
        return _empty_summary(project=project, chapter=chapter, config=config)

    shot_ids = [shot.id for shot in shots]
    details = await _details_by_shot(db, shot_ids)
    dialogue_by_shot = await _dialogue_by_shot(db, shot_ids)
    frame_refs_by_shot = await _frame_refs_by_shot(db, shot_ids)
    character_ids_by_shot = await _character_ids_by_shot(db, shot_ids)

    all_character_ids = {
        character_id
        for ids in character_ids_by_shot.values()
        for character_id in ids
        if character_id
    }
    mood_by_scene: dict[str, str] = {}
    scene_ids: set[str] = set()
    for detail in details.values():
        if detail.scene_id:
            scene_ids.add(detail.scene_id)
            mood_tags = [str(item) for item in (detail.mood_tags or []) if str(item).strip()]
            if mood_tags:
                mood_by_scene[detail.scene_id] = ",".join(mood_tags)

    character_bibles, character_assets = await _character_bibles_and_assets(db, character_ids=all_character_ids)
    scene_bibles, scene_assets = await _scene_bibles_and_assets(db, scene_ids=scene_ids, fallback_mood_by_scene=mood_by_scene)
    character_bibles_by_id = {item.id: item for item in character_bibles}
    scene_bibles_by_id = {item.id: item for item in scene_bibles}

    plannable: list[StudioShot] = []
    ready_shots = 0
    generated_video_count = 0
    generated_shot_ids: set[str] = set()
    for shot in shots:
        detail = details.get(shot.id)
        if _enum_value(shot.status) == ShotStatus.ready.value:
            ready_shots += 1
        if shot.generated_video_file_id:
            generated_video_count += 1
            generated_shot_ids.add(shot.id)
        if detail is None or not detail.duration or detail.duration <= 0:
            continue
        mood_tags = [str(item) for item in (detail.mood_tags or []) if str(item).strip()]
        action_text = detail.description or shot.script_excerpt or shot.title
        plannable.append(
            StudioShot(
                id=shot.id,
                project_id=project.id,
                chapter_id=chapter.id,
                index=shot.index,
                title=shot.title,
                summary=action_text,
                scene_id=detail.scene_id,
                character_ids=character_ids_by_shot.get(shot.id, []),
                dialogue=dialogue_by_shot.get(shot.id, []),
                camera={
                    "framing": _enum_value(detail.camera_shot),
                    "angle": _enum_value(detail.angle),
                    "movement": _enum_value(detail.movement),
                    "lens": config.lens,
                    "emotion": ",".join(mood_tags) if mood_tags else "neutral",
                    "pacing": "steady",
                    "action_beats": list(detail.action_beats or []),
                },
                duration=float(detail.duration),
                reference_media=frame_refs_by_shot.get(shot.id, []),
                readiness_state=_enum_value(shot.status),
                is_generation_ready=_enum_value(shot.status) == ShotStatus.ready.value,
                metadata={"generated_video_file_id": shot.generated_video_file_id},
            )
        )

    task_metrics_by_shot = await _task_qa_metrics_by_shot(db, list(generated_shot_ids))
    qa_metrics_by_shot = {
        shot.id: task_metrics_by_shot.get(shot.id)
        or _estimate_generated_shot_qa_metrics(
            shot=shot,
            character_bibles_by_id=character_bibles_by_id,
            scene_bibles_by_id=scene_bibles_by_id,
        )
        for shot in plannable
        if shot.id in generated_shot_ids
    }

    studio_project = StudioProject(
        id=project.id,
        title=project.name,
        description=project.description,
        style=_enum_value(project.style),
        visual_style=_enum_value(project.visual_style),
    )
    studio_chapter = StudioChapter(
        id=chapter.id,
        project_id=project.id,
        title=chapter.title,
        order=chapter.index,
        raw_text=chapter.raw_text,
        condensed_text=chapter.condensed_text,
    )

    plan = ClosedLoopProductionPlanner().plan_chapter(
        project=studio_project,
        chapter=studio_chapter,
        shots=plannable,
        assets=[*character_assets, *scene_assets],
        character_bibles=character_bibles,
        scene_bibles=scene_bibles,
        provider=config.runtime_provider,
        model=config.runtime_model,
        output_dir=config.output_dir,
        qa_metrics_by_shot=qa_metrics_by_shot,
        render_results=[
            RenderResult(shot.id, f"file:{shot.generated_video_file_id}", config.runtime_provider, {})
            for shot in shots
            if shot.generated_video_file_id
        ],
        export_output_path=f"{config.output_dir}/exports/{chapter.id}.mp4",
        qa_threshold=config.qa_threshold,
        auto_retry=config.auto_retry,
        retry_limit=config.retry_limit,
    )
    summary = plan.as_dict()

    if generated_video_count <= 0:
        summary["qa"] = {"passed": False, "reports": []}
        summary["retry_requests"] = []
        summary["post_production"] = {"enabled": False, "output_path": None}
    else:
        qa_reports = [
            report
            for report in (summary.get("qa", {}).get("reports") if isinstance(summary.get("qa"), dict) else []) or []
            if report.get("shot_id") in generated_shot_ids
        ]
        summary["qa"] = {
            "passed": bool(qa_reports) and all(bool(report.get("passed")) for report in qa_reports),
            "reports": qa_reports,
        }
        if not config.auto_retry:
            summary["retry_requests"] = []
        else:
            summary["retry_requests"] = [
                retry
                for retry in (summary.get("retry_requests") or [])
                if retry.get("shot_id") in generated_shot_ids
            ][: config.retry_limit]
        if len(plannable) <= 0 or generated_video_count < len(plannable):
            summary["post_production"] = {"enabled": False, "output_path": None}

    render_request_count = len(summary.get("render_requests") or [])
    qa_reports = summary.get("qa", {}).get("reports") if isinstance(summary.get("qa"), dict) else []
    retry_count = len(summary.get("retry_requests") or [])
    workflow_status = _workflow_status(
        chapter=chapter,
        total_shots=len(shots),
        plannable_shots=len(plannable),
        ready_shots=ready_shots,
        linked_character_count=len(all_character_ids),
        linked_scene_count=len(scene_ids),
        render_request_count=render_request_count,
        qa_report_count=len(qa_reports or []),
        retry_count=retry_count,
        generated_video_count=generated_video_count,
    )

    summary["metadata"] = {
        **dict(summary.get("metadata") or {}),
        "mode": "jellyfish_project_context",
        "scope": "project",
        "shot_count": len(shots),
        "plannable_shot_count": len(plannable),
        "ready_shot_count": ready_shots,
        "generated_video_count": generated_video_count,
        "linked_character_count": len(all_character_ids),
        "linked_scene_count": len(scene_ids),
        "config": config.model_dump(),
        "workflow_status": workflow_status,
        "next_action": _next_action(
            total_shots=len(shots),
            plannable_shots=len(plannable),
            ready_shots=ready_shots,
            render_request_count=render_request_count,
            generated_video_count=generated_video_count,
        ),
    }
    return summary


async def build_project_film_engine_series_index(
    db: AsyncSession,
    *,
    project_id: str,
) -> dict[str, Any]:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=entity_not_found("Project"))

    config = get_film_engine_config_from_project(project)
    chapters = list(
        (
            await db.execute(
                select(Chapter).where(Chapter.project_id == project.id).order_by(Chapter.index)
            )
        )
        .scalars()
        .all()
    )
    if not chapters:
        return {
            "project": {"id": project.id, "title": project.name},
            "config": config.model_dump(),
            "episode_count": 0,
            "all_chapters_done": False,
            "totals": {
                "shot_count": 0,
                "plannable_shot_count": 0,
                "ready_shot_count": 0,
                "generated_video_count": 0,
                "retry_count": 0,
                "qa_report_count": 0,
            },
            "next_action": {
                "key": "create_chapter",
                "label": "创建章节",
                "hint": "先建立第一集/第一章，再进入 Film Engine 多集生产闭环。",
            },
            "chapters": [],
        }

    from src.film_engine.studio import build_production_workflow_stage_index, build_stage_index

    chapter_rows: list[dict[str, Any]] = []
    totals = {
        "shot_count": 0,
        "plannable_shot_count": 0,
        "ready_shot_count": 0,
        "generated_video_count": 0,
        "retry_count": 0,
        "qa_report_count": 0,
    }
    for chapter in chapters:
        summary = await build_project_film_engine_summary(db, project_id=project.id, chapter_id=chapter.id)
        metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
        qa = summary.get("qa") if isinstance(summary.get("qa"), dict) else {}
        qa_reports = qa.get("reports") if isinstance(qa, dict) else []
        retry_requests = summary.get("retry_requests") or []
        stages = build_stage_index(summary)
        workflow_stages = build_production_workflow_stage_index(summary)
        for key in ("shot_count", "plannable_shot_count", "ready_shot_count", "generated_video_count"):
            totals[key] += int(metadata.get(key) or 0)
        totals["retry_count"] += len(retry_requests)
        totals["qa_report_count"] += len(qa_reports or [])
        chapter_rows.append(
            {
                "id": chapter.id,
                "index": chapter.index,
                "title": chapter.title,
                "shot_count": int(metadata.get("shot_count") or 0),
                "plannable_shot_count": int(metadata.get("plannable_shot_count") or 0),
                "ready_shot_count": int(metadata.get("ready_shot_count") or 0),
                "generated_video_count": int(metadata.get("generated_video_count") or 0),
                "retry_count": len(retry_requests),
                "qa_report_count": len(qa_reports or []),
                "qa_passed": bool(qa.get("passed")),
                "post_production_enabled": bool((summary.get("post_production") or {}).get("enabled")),
                "stage_done_count": sum(1 for stage in stages if stage.status == "done"),
                "stage_total": len(stages),
                "workflow_done_count": sum(1 for stage in workflow_stages if stage.status == "done"),
                "workflow_total": len(workflow_stages),
                "all_stages_done": all(stage.status == "done" for stage in stages),
                "next_action": metadata.get("next_action") or {},
            }
        )

    first_pending = next((item for item in chapter_rows if not item["all_stages_done"]), None)
    next_action = (
        first_pending.get("next_action")
        if first_pending
        else {
            "key": "series_export",
            "label": "整季导出",
            "hint": "所有章节 Film Engine 证据已齐备，可进入最终剪辑与整季交付。",
        }
    )
    return {
        "project": {"id": project.id, "title": project.name},
        "config": config.model_dump(),
        "episode_count": len(chapter_rows),
        "all_chapters_done": bool(chapter_rows) and all(item["all_stages_done"] for item in chapter_rows),
        "totals": totals,
        "next_action": next_action,
        "chapters": chapter_rows,
    }
