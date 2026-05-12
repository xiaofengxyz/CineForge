from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base
from app.models.studio import (
    CameraAngle,
    CameraMovement,
    CameraShotType,
    Chapter,
    Character,
    CharacterImage,
    FileItem,
    FileType,
    FileUsage,
    Project,
    ProjectStyle,
    ProjectVisualStyle,
    Scene,
    SceneImage,
    Shot,
    ShotCharacterLink,
    ShotDetail,
    ShotStatus,
)
from app.models.task import GenerationDeliveryMode, GenerationTask, GenerationTaskStatus
from app.models.task_links import GenerationTaskLink
from app.services.film.engine_state import (
    FilmEngineConfigUpdate,
    build_project_film_engine_summary,
    build_project_film_engine_series_index,
    create_film_engine_retry_task,
    evaluate_shot_visual_qa,
    get_project_film_engine_config,
    update_project_film_engine_config,
)
from app.services.film.stock_assets import StockMediaItem, collect_stock_assets
from app.services.film.visual_qa import VisualQAEvaluation


async def _build_session() -> tuple[AsyncSession, object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return session_local(), engine


def test_film_engine_demo_plan_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/film/engine/demo-plan")

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    data = body["data"]
    assert data["metadata"]["mode"] == "closed_loop_industrial_batch"
    assert data["metadata"]["retry_count"] == 1
    assert data["workflow"][0] == "script_breakdown"
    assert data["workflow"][-1] == "final_export"
    assert data["qa"]["passed"] is False


def test_film_engine_stage_index_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/film/engine/stage-index")

    assert response.status_code == 200
    body = response.json()
    stages = body["data"]["stages"]
    assert len(stages) == 9
    assert body["data"]["all_stages_done"] is True
    assert stages[0]["id"] == "runtime_adapter"
    assert stages[0]["owner"] == "Runtime"
    assert stages[-1]["id"] == "film_state_engine"
    assert stages[-1]["status"] == "done"
    assert stages[-1]["ui_surface"] == "/film-engine"
    assert len(body["data"]["workflow_stages"]) == 9
    assert body["data"]["workflow_stages"][0]["id"] == "script_breakdown"
    assert body["data"]["workflow_stages"][-1]["id"] == "final_export"


def test_text_to_drama_plan_endpoint_returns_executable_plan_without_secret_leak(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/film/engine/text-to-drama-plan",
        json={
            "source_text": "Ari finds a key in a neon alley and chooses to save the city.",
            "title": "Neon Trial",
            "config": {
                "persist": False,
                "max_chapters": 1,
                "shots_per_chapter": 1,
                "runtime_profiles": {
                    "video": {
                        "provider": "kling",
                        "model": "kling-v1",
                        "base_url": "https://video.example",
                        "api_key": "secret-token",
                    }
                },
            },
        },
    )

    assert response.status_code == 200
    assert "secret-token" not in response.text
    body = response.json()
    data = body["data"]
    assert data["status"] == "completed"
    assert data["artifacts"]["novel_plan"]["chapters"]
    assert data["artifacts"]["video_plans"][0]["render_requests"]
    assert data["workflow_control"]["done_count"] == 9


def test_stock_asset_collect_endpoint_returns_preview_items_without_persisting(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_collect(self: object, *, query: str, image_count: int, video_count: int) -> list[StockMediaItem]:
        """Return deterministic media so the API test never depends on the network."""
        assert query == "neon alley"
        assert image_count == 1
        assert video_count == 1
        return [
            StockMediaItem(
                id="image-1",
                media_type="image",
                title="Neon image",
                provider="wikimedia_commons",
                source_url="https://example.test/neon.jpg",
                thumbnail_url="https://example.test/neon-thumb.jpg",
                license_page_url="https://commons.wikimedia.org/wiki/File:Neon.jpg",
            ),
            StockMediaItem(
                id="video-1",
                media_type="video",
                title="Neon video",
                provider="wikimedia_commons",
                source_url="https://example.test/neon.webm",
                thumbnail_url="https://example.test/neon-video-thumb.jpg",
                license_page_url="https://commons.wikimedia.org/wiki/File:Neon.webm",
            ),
        ]

    monkeypatch.setattr("app.services.film.stock_assets.CommonsStockMediaClient.collect", fake_collect)

    response = client.post(
        "/api/v1/film/engine/stock-assets/collect",
        json={"query": "neon alley", "image_count": 1, "video_count": 1, "persist": False},
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["persisted"] is False
    assert data["item_count"] == 2
    assert data["items"][0]["file_id"].startswith("stock_")
    assert data["items"][1]["media_type"] == "video"
    assert data["sources"][0]["name"] == "Wikimedia Commons"


@pytest.mark.asyncio
async def test_project_film_engine_config_is_persisted_in_project_stats() -> None:
    db, engine = await _build_session()
    async with db:
        project = Project(
            id="film-project",
            name="漫剧项目",
            description="",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
            stats={},
        )
        db.add(project)
        await db.commit()

        default_config = await get_project_film_engine_config(db, project_id=project.id)
        assert default_config.enabled is True
        assert default_config.runtime_provider == "kling"

        updated = await update_project_film_engine_config(
            db,
            project_id=project.id,
            update=FilmEngineConfigUpdate(
                runtime_provider="veo",
                runtime_model="veo-3",
                reference_mode="text_only",
                qa_threshold=0.8,
            ),
        )

        assert updated.runtime_provider == "veo"
        assert updated.runtime_model == "veo-3"
        assert project.stats["film_engine_config"]["reference_mode"] == "text_only"
        assert project.stats["film_engine_config"]["qa_threshold"] == 0.8
    await engine.dispose()


@pytest.mark.asyncio
async def test_stock_asset_collection_persists_project_files_idempotently() -> None:
    class FakeStockClient:
        async def collect(self, *, query: str, image_count: int, video_count: int) -> list[StockMediaItem]:
            """Return stable stock results and assert chapter text produced the query."""
            assert "霓虹街巷" in query
            assert image_count == 1
            assert video_count == 1
            return [
                StockMediaItem(
                    id="commons-image",
                    media_type="image",
                    title="霓虹街巷参考图",
                    provider="wikimedia_commons",
                    source_url="https://example.test/stock/neon.jpg",
                    thumbnail_url="https://example.test/stock/neon-thumb.jpg",
                    license_page_url="https://commons.wikimedia.org/wiki/File:Neon.jpg",
                    tags=["stock", "image"],
                ),
                StockMediaItem(
                    id="commons-video",
                    media_type="video",
                    title="霓虹街巷动态参考",
                    provider="wikimedia_commons",
                    source_url="https://example.test/stock/neon.webm",
                    thumbnail_url="https://example.test/stock/neon-video-thumb.jpg",
                    license_page_url="https://commons.wikimedia.org/wiki/File:Neon.webm",
                    tags=["stock", "video"],
                ),
            ]

    db, engine = await _build_session()
    async with db:
        project = Project(
            id="film-project",
            name="漫剧项目",
            description="雨夜追逐",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
            stats={},
        )
        chapter = Chapter(
            id="chapter-1",
            project_id=project.id,
            index=1,
            title="第一章",
            raw_text="陆远进入霓虹街巷寻找线索。",
            condensed_text="霓虹街巷追逐。",
        )
        db.add_all([project, chapter])
        await db.commit()

        first = await collect_stock_assets(
            db,
            project_id=project.id,
            chapter_id=chapter.id,
            query=None,
            image_count=1,
            video_count=1,
            persist=True,
            client=FakeStockClient(),
        )
        second = await collect_stock_assets(
            db,
            project_id=project.id,
            chapter_id=chapter.id,
            query=None,
            image_count=1,
            video_count=1,
            persist=True,
            client=FakeStockClient(),
        )

        files = (await db.execute(select(FileItem).order_by(FileItem.id))).scalars().all()
        usages = (await db.execute(select(FileUsage).order_by(FileUsage.file_id))).scalars().all()

        assert first["persisted"] is True
        assert first["created_file_count"] == 2
        assert second["created_file_count"] == 0
        assert len(files) == 2
        assert {item.type for item in files} == {FileType.image, FileType.video}
        assert all("film_engine_bootstrap" in item.tags for item in files)
        assert len(usages) == 2
        assert {usage.project_id for usage in usages} == {project.id}
        assert {usage.chapter_id for usage in usages} == {chapter.id}
    await engine.dispose()


@pytest.mark.asyncio
async def test_project_stage_index_uses_real_chapter_context() -> None:
    db, engine = await _build_session()
    async with db:
        project = Project(
            id="film-project",
            name="漫剧项目",
            description="",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
            stats={},
        )
        chapter = Chapter(
            id="chapter-1",
            project_id=project.id,
            index=1,
            title="第一章",
            raw_text="主角进入霓虹街巷。",
            condensed_text="主角进入霓虹街巷。",
        )
        scene = Scene(
            id="scene-1",
            name="霓虹街巷",
            description="雨夜霓虹街巷",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
            tags=["neon_key", "suspense"],
        )
        character = Character(
            id="char-1",
            project_id=project.id,
            name="陆远",
            description="年轻侦探",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
        )
        shot = Shot(
            id="shot-1",
            chapter_id=chapter.id,
            index=1,
            title="镜头一",
            status=ShotStatus.ready,
            script_excerpt="陆远停在霓虹招牌下。",
            generated_video_file_id="video-1",
        )
        detail = ShotDetail(
            id=shot.id,
            camera_shot=CameraShotType.ms,
            angle=CameraAngle.eye_level,
            movement=CameraMovement.dolly_in,
            scene_id=scene.id,
            duration=4,
            mood_tags=["tense"],
            description="陆远停在霓虹招牌下，抬头观察街角。",
            action_beats=["停步", "抬头", "观察"],
        )
        db.add_all(
            [
                FileItem(id="char-img", type=FileType.image, name="char", storage_key="char.png"),
                FileItem(id="scene-img", type=FileType.image, name="scene", storage_key="scene.png"),
                FileItem(id="video-1", type=FileType.video, name="shot", storage_key="shot.mp4"),
                project,
                chapter,
                scene,
                character,
                shot,
                detail,
                CharacterImage(character_id=character.id, file_id="char-img", is_primary=True),
                SceneImage(scene_id=scene.id, file_id="scene-img"),
                ShotCharacterLink(shot_id=shot.id, character_id=character.id, index=1),
            ]
        )
        await db.commit()

        summary = await build_project_film_engine_summary(db, project_id=project.id, chapter_id=chapter.id)
        from src.film_engine.studio import build_production_workflow_stage_index, build_stage_index

        assert summary["project"]["id"] == project.id
        assert summary["chapter"]["id"] == chapter.id
        assert summary["metadata"]["scope"] == "project"
        assert summary["metadata"]["shot_count"] == 1
        assert summary["metadata"]["plannable_shot_count"] == 1
        assert summary["metadata"]["generated_video_count"] == 1
        assert summary["render_requests"][0]["shot_id"] == shot.id
        assert summary["qa"]["reports"][0]["passed"] is True
        assert summary["post_production"]["enabled"] is True
        assert all(stage.status == "done" for stage in build_stage_index(summary))
        assert all(stage.status == "done" for stage in build_production_workflow_stage_index(summary))
    await engine.dispose()


@pytest.mark.asyncio
async def test_project_stage_index_respects_task_qa_metrics_retry_limit_and_partial_export() -> None:
    db, engine = await _build_session()
    async with db:
        project = Project(
            id="film-project",
            name="漫剧项目",
            description="",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
            stats={"film_engine_config": {"qa_threshold": 0.8, "retry_limit": 1, "auto_retry": True}},
        )
        chapter = Chapter(
            id="chapter-1",
            project_id=project.id,
            index=1,
            title="第一章",
            raw_text="主角进入霓虹街巷。",
            condensed_text="主角进入霓虹街巷。",
        )
        scene = Scene(
            id="scene-1",
            name="霓虹街巷",
            description="雨夜霓虹街巷",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
            tags=["neon_key", "suspense"],
        )
        character = Character(
            id="char-1",
            project_id=project.id,
            name="陆远",
            description="年轻侦探",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
        )
        shot_1 = Shot(
            id="shot-1",
            chapter_id=chapter.id,
            index=1,
            title="镜头一",
            status=ShotStatus.ready,
            script_excerpt="陆远停在霓虹招牌下。",
            generated_video_file_id="video-1",
        )
        shot_2 = Shot(
            id="shot-2",
            chapter_id=chapter.id,
            index=2,
            title="镜头二",
            status=ShotStatus.ready,
            script_excerpt="陆远走入巷口。",
        )
        task = GenerationTask(
            id="task-video-1",
            mode=GenerationDeliveryMode.async_polling,
            task_kind="video_generation",
            status=GenerationTaskStatus.succeeded,
            progress=100,
            payload={},
            result={"qa_metrics": {"face_similarity": 0.55, "outfit_similarity": 0.70, "clip_score": 0.62}},
        )
        db.add_all(
            [
                FileItem(id="video-1", type=FileType.video, name="shot", storage_key="shot.mp4"),
                project,
                chapter,
                scene,
                character,
                shot_1,
                shot_2,
                ShotDetail(
                    id=shot_1.id,
                    camera_shot=CameraShotType.ms,
                    angle=CameraAngle.eye_level,
                    movement=CameraMovement.dolly_in,
                    scene_id=scene.id,
                    duration=4,
                    mood_tags=["tense"],
                    description="陆远停在霓虹招牌下。",
                    action_beats=["停步", "抬头"],
                ),
                ShotDetail(
                    id=shot_2.id,
                    camera_shot=CameraShotType.ms,
                    angle=CameraAngle.eye_level,
                    movement=CameraMovement.dolly_in,
                    scene_id=scene.id,
                    duration=4,
                    mood_tags=["tense"],
                    description="陆远走入巷口。",
                    action_beats=["迈步", "回望"],
                ),
                ShotCharacterLink(shot_id=shot_1.id, character_id=character.id, index=1),
                ShotCharacterLink(shot_id=shot_2.id, character_id=character.id, index=1),
                task,
                GenerationTaskLink(
                    task_id=task.id,
                    resource_type="video",
                    relation_type="video",
                    relation_entity_id=shot_1.id,
                    file_id="video-1",
                ),
            ]
        )
        await db.commit()

        summary = await build_project_film_engine_summary(db, project_id=project.id, chapter_id=chapter.id)
        from src.film_engine.studio import build_production_workflow_stage_index

        assert summary["metadata"]["plannable_shot_count"] == 2
        assert summary["metadata"]["generated_video_count"] == 1
        assert len(summary["qa"]["reports"]) == 1
        assert summary["qa"]["reports"][0]["passed"] is False
        assert len(summary["retry_requests"]) == 1
        assert summary["post_production"]["enabled"] is False
        final_stage = [stage for stage in build_production_workflow_stage_index(summary) if stage.id == "final_export"][0]
        assert final_stage.status == "pending"
    await engine.dispose()


@pytest.mark.asyncio
async def test_manual_film_visual_qa_persists_advanced_metrics_for_existing_video(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Manual visual QA should write OpenCV, InsightFace, and CLIP metrics."""
    db, engine = await _build_session()
    async with db:
        project = Project(
            id="film-project",
            name="漫剧项目",
            description="",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
            stats={},
        )
        chapter = Chapter(
            id="chapter-1",
            project_id=project.id,
            index=1,
            title="第一章",
            raw_text="主角进入霓虹街巷。",
            condensed_text="主角进入霓虹街巷。",
        )
        shot = Shot(
            id="shot-1",
            chapter_id=chapter.id,
            index=1,
            title="镜头一",
            status=ShotStatus.ready,
            script_excerpt="陆远停在霓虹招牌下。",
            generated_video_file_id="video-1",
        )
        character = Character(
            id="char-1",
            project_id=project.id,
            name="陆远",
            description="年轻侦探",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
        )
        db.add_all(
            [
                FileItem(id="video-1", type=FileType.video, name="shot", storage_key="shot.mp4"),
                FileItem(id="char-img", type=FileType.image, name="char", storage_key="char.png"),
                project,
                chapter,
                shot,
                character,
                CharacterImage(character_id=character.id, file_id="char-img", is_primary=True),
                ShotCharacterLink(shot_id=shot.id, character_id=character.id, index=1),
                ShotDetail(
                    id=shot.id,
                    camera_shot=CameraShotType.ms,
                    angle=CameraAngle.eye_level,
                    movement=CameraMovement.dolly_in,
                    duration=4,
                    mood_tags=["tense"],
                    description="陆远停在霓虹招牌下。",
                    action_beats=["停步", "抬头"],
                ),
            ]
        )
        await db.commit()

        async def fake_evaluate_file_item_with_film_visual_qa(*args: object, **kwargs: object) -> VisualQAEvaluation:
            """Return deterministic Film Visual QA metrics without object storage."""
            assert kwargs["character_reference_file_ids_by_id"] == {"char-1": ["char-img"]}
            assert "陆远停在霓虹招牌下" in kwargs["prompt_text"]
            return VisualQAEvaluation(
                metrics={"lighting_similarity": 0.91, "face_similarity": 0.88, "clip_score": 0.83},
                details={"stub": True},
                evaluator="film_visual_qa",
            )

        monkeypatch.setattr(
            "app.services.film.engine_state.evaluate_file_item_with_film_visual_qa",
            fake_evaluate_file_item_with_film_visual_qa,
        )

        result = await evaluate_shot_visual_qa(db, shot_id=shot.id)
        task = (
            await db.execute(
                select(GenerationTask).where(GenerationTask.task_kind == "film_visual_qa")
            )
        ).scalars().one()
        summary = await build_project_film_engine_summary(db, project_id=project.id, chapter_id=chapter.id)

        assert result["status"] == "succeeded"
        assert result["metrics"]["clip_score"] == 0.83
        assert result["metrics"]["face_similarity"] == 0.88
        assert task.result["film_engine_qa_metrics"]["lighting_similarity"] == 0.91
        assert task.result["film_engine_qa_metrics"]["face_similarity"] == 0.88
        assert summary["qa"]["reports"][0]["metrics"]["clip_score"] == 0.83
        assert summary["qa"]["reports"][0]["metrics"]["face_similarity"] == 0.88
    await engine.dispose()


@pytest.mark.asyncio
async def test_film_engine_retry_task_creates_real_video_generation_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Film Engine retry request should become a persisted video_generation task."""
    db, engine = await _build_session()
    async with db:
        project = Project(
            id="film-project",
            name="漫剧项目",
            description="",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
            default_video_ratio="9:16",
            stats={"film_engine_config": {"reference_mode": "text_only", "qa_threshold": 0.8}},
        )
        chapter = Chapter(
            id="chapter-1",
            project_id=project.id,
            index=1,
            title="第一章",
            raw_text="主角进入霓虹街巷。",
            condensed_text="主角进入霓虹街巷。",
        )
        shot = Shot(
            id="shot-1",
            chapter_id=chapter.id,
            index=1,
            title="镜头一",
            status=ShotStatus.ready,
            script_excerpt="陆远停在霓虹招牌下。",
            generated_video_file_id="video-1",
        )
        qa_task = GenerationTask(
            id="task-video-1",
            mode=GenerationDeliveryMode.async_polling,
            task_kind="video_generation",
            status=GenerationTaskStatus.succeeded,
            progress=100,
            payload={},
            result={"film_engine_qa_metrics": {"lighting_similarity": 0.45, "clip_score": 0.42}},
        )
        db.add_all(
            [
                FileItem(id="video-1", type=FileType.video, name="shot", storage_key="shot.mp4"),
                project,
                chapter,
                shot,
                ShotDetail(
                    id=shot.id,
                    camera_shot=CameraShotType.ms,
                    angle=CameraAngle.eye_level,
                    movement=CameraMovement.dolly_in,
                    duration=4,
                    mood_tags=["tense"],
                    description="陆远停在霓虹招牌下。",
                    action_beats=["停步", "抬头"],
                ),
                qa_task,
                GenerationTaskLink(
                    task_id=qa_task.id,
                    resource_type="video",
                    relation_type="video",
                    relation_entity_id=shot.id,
                    file_id="video-1",
                ),
            ]
        )
        await db.commit()

        async def fake_build_run_args(*args: object, **kwargs: object) -> dict:
            """Return minimal worker run args without requiring model settings."""
            return {
                "shot_id": kwargs["shot_id"],
                "input": {"prompt": kwargs["prompt"], "ratio": kwargs["ratio"]},
                "film_engine_qa_context": {"reference_file_ids": kwargs["images"]},
            }

        dispatched_task_ids: list[str] = []

        def fake_enqueue_task_execution(task_id: str) -> object:
            """Record worker dispatch without requiring Redis/Celery in unit tests."""
            dispatched_task_ids.append(task_id)
            return object()

        monkeypatch.setattr("app.services.film.engine_state.build_run_args", fake_build_run_args)
        monkeypatch.setattr("app.services.film.engine_state.enqueue_task_execution", fake_enqueue_task_execution)

        result = await create_film_engine_retry_task(
            db,
            project_id=project.id,
            chapter_id=chapter.id,
            shot_id=shot.id,
        )
        retry_task = await db.get(GenerationTask, result["task_id"])

        assert retry_task is not None
        assert retry_task.task_kind == "video_generation"
        assert retry_task.payload["run_args"]["film_engine_retry"]["reason_codes"] == [
            "lighting_mismatch",
            "weak_prompt_alignment",
        ]
        assert result["ratio"] == "9:16"
        assert dispatched_task_ids == [result["task_id"]]
    await engine.dispose()


@pytest.mark.asyncio
async def test_project_series_index_aggregates_multi_episode_status() -> None:
    db, engine = await _build_session()
    async with db:
        project = Project(
            id="film-project",
            name="漫剧项目",
            description="",
            style=ProjectStyle.guoman,
            visual_style=ProjectVisualStyle.anime,
            stats={},
        )
        chapter_1 = Chapter(
            id="chapter-1",
            project_id=project.id,
            index=1,
            title="第一章",
            raw_text="第一集文本",
            condensed_text="第一集文本",
        )
        chapter_2 = Chapter(
            id="chapter-2",
            project_id=project.id,
            index=2,
            title="第二章",
            raw_text="第二集文本",
            condensed_text="第二集文本",
        )
        shot = Shot(
            id="shot-1",
            chapter_id=chapter_1.id,
            index=1,
            title="镜头一",
            status=ShotStatus.ready,
            script_excerpt="陆远停在霓虹招牌下。",
            generated_video_file_id="video-1",
        )
        db.add_all(
            [
                FileItem(id="video-1", type=FileType.video, name="shot", storage_key="shot.mp4"),
                project,
                chapter_1,
                chapter_2,
                shot,
                ShotDetail(
                    id=shot.id,
                    camera_shot=CameraShotType.ms,
                    angle=CameraAngle.eye_level,
                    movement=CameraMovement.dolly_in,
                    duration=4,
                    mood_tags=["tense"],
                    description="陆远停在霓虹招牌下。",
                    action_beats=["停步", "抬头"],
                ),
            ]
        )
        await db.commit()

        series = await build_project_film_engine_series_index(db, project_id=project.id)

        assert series["episode_count"] == 2
        assert series["totals"]["shot_count"] == 1
        assert series["totals"]["generated_video_count"] == 1
        assert series["chapters"][0]["id"] == chapter_1.id
        assert series["chapters"][1]["next_action"]["key"] == "extract_shots"
        assert series["all_chapters_done"] is False
    await engine.dispose()
