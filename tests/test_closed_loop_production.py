from src.film_engine import (
    CharacterBible,
    ClosedLoopProductionPlanner,
    RenderResult,
    SceneBible,
    StudioAsset,
    StudioChapter,
    StudioProject,
    StudioShot,
)


def _fixture():
    project = StudioProject(id="project_001", title="Neon Trial")
    chapter = StudioChapter(id="chapter_001", project_id=project.id, title="Pilot")
    assets = [
        StudioAsset(
            id="char_001",
            kind="character",
            name="Ari",
            reference_media=["refs/ari_asset.png"],
        ),
        StudioAsset(
            id="scene_001",
            kind="scene",
            name="Neon alley",
            reference_media=["refs/alley_asset.png"],
            metadata={"lighting": "neon_blue"},
        ),
    ]
    character_bibles = [
        CharacterBible(
            id="char_001",
            name="Ari",
            reference_media=["refs/ari_bible.png"],
            outfits={"coat_black": "black rain coat"},
            default_outfit="coat_black",
            voice_id="voice_ari",
            negative_terms=["wrong face"],
        )
    ]
    scene_bibles = [
        SceneBible(
            id="scene_001",
            name="Neon alley",
            lighting="neon_blue",
            mood="suspense",
            reference_media=["refs/alley_bible.png"],
        )
    ]
    shots = [
        StudioShot(
            id="shot_001",
            project_id=project.id,
            chapter_id=chapter.id,
            index=1,
            scene_id="scene_001",
            character_ids=["char_001"],
            dialogue=["Ari: Keep walking."],
            camera={
                "framing": "medium_closeup",
                "movement": "dolly_in",
                "lens": "85mm",
                "emotion": "wary",
                "pacing": "slow",
            },
            duration=4,
            readiness_state="ready",
        ),
        StudioShot(
            id="shot_002",
            project_id=project.id,
            chapter_id=chapter.id,
            index=2,
            scene_id="scene_001",
            character_ids=["char_001"],
            camera={
                "framing": "wide",
                "movement": "track",
                "lens": "35mm",
                "emotion": "urgent",
            },
            duration=3,
            readiness_state="ready",
        ),
    ]
    return project, chapter, assets, character_bibles, scene_bibles, shots


def test_closed_loop_plan_compiles_render_requests_qa_and_retry_requests():
    project, chapter, assets, character_bibles, scene_bibles, shots = _fixture()

    plan = ClosedLoopProductionPlanner().plan_chapter(
        project=project,
        chapter=chapter,
        shots=shots,
        assets=assets,
        character_bibles=character_bibles,
        scene_bibles=scene_bibles,
        provider="kling",
        model="kling-v1",
        output_dir="output/renders",
        qa_metrics_by_shot={
            "shot_001": {
                "face_similarity": 0.61,
                "outfit_similarity": 0.82,
                "clip_score": 0.52,
            }
        },
    )

    assert [node.system for node in plan.workflow.topological_order()] == [
        "script_breakdown",
        "shot_preparation",
        "asset_consistency",
        "film_state",
        "prompt_compiler",
        "runtime_adapter",
        "qa_engine",
        "retry_engine",
        "final_export",
    ]
    assert len(plan.render_requests) == 2
    assert plan.qa_passed is False
    assert plan.metadata["retry_count"] == 1
    assert plan.shot_plans[0].qa_report.issues[0].code == "low_face_similarity"
    assert plan.retry_requests[0].parameters["reference_strength"] == "high"
    assert plan.retry_requests[0].parameters["retry_attempt"] == 2
    assert "Increase reference strength for face_similarity." in plan.retry_requests[0].prompt
    assert plan.render_requests[0].references == [
        "refs/ari_asset.png",
        "refs/alley_asset.png",
        "refs/ari_bible.png",
        "refs/alley_bible.png",
    ]
    assert "wrong face" in plan.shot_plans[0].compiled_prompt.negative_text


def test_closed_loop_plan_adds_post_production_when_render_results_exist():
    project, chapter, assets, character_bibles, scene_bibles, shots = _fixture()

    plan = ClosedLoopProductionPlanner().plan_chapter(
        project=project,
        chapter=chapter,
        shots=shots,
        assets=assets,
        character_bibles=character_bibles,
        scene_bibles=scene_bibles,
        provider="kling",
        model="kling-v1",
        output_dir="output/renders",
        render_results=[
            RenderResult("shot_001", "output/renders/shot_001.mp4", "kling", {"duration": 4}),
            RenderResult("shot_002", "output/renders/shot_002.mp4", "kling", {"duration": 3}),
        ],
        export_output_path="output/exports/chapter_001.mp4",
    )

    assert plan.qa_passed is True
    assert plan.post_production_plan is not None
    assert plan.post_production_plan.metadata["clip_count"] == 2
    assert [step.system for step in plan.post_production_plan.steps][-2:] == [
        "ffmpeg_concat",
        "export",
    ]
    assert plan.post_production_plan.output_path == "output/exports/chapter_001.mp4"
