from __future__ import annotations

from .core import (
    CharacterBible,
    ClosedLoopProductionPlanner,
    RenderResult,
    SceneBible,
    StudioAsset,
    StudioChapter,
    StudioProject,
    StudioShot,
)


def build_demo_plan_summary() -> dict[str, object]:
    project = StudioProject(id="project_001", title="Neon Trial")
    chapter = StudioChapter(id="chapter_001", project_id=project.id, title="Pilot")
    assets = [
        StudioAsset("char_001", "character", "Ari", reference_media=["refs/ari_asset.png"]),
        StudioAsset("scene_001", "scene", "Neon alley", reference_media=["refs/alley_asset.png"], metadata={"lighting": "neon_blue"}),
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
            camera={"framing": "medium_closeup", "movement": "dolly_in", "lens": "85mm", "emotion": "wary", "pacing": "slow"},
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
            camera={"framing": "wide", "movement": "track", "lens": "35mm", "emotion": "urgent"},
            duration=3,
            readiness_state="ready",
        ),
    ]
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
            "shot_001": {"face_similarity": 0.61, "outfit_similarity": 0.82, "clip_score": 0.52}
        },
        render_results=[
            RenderResult("shot_001", "output/renders/shot_001.mp4", "kling", {"duration": 4}),
            RenderResult("shot_002", "output/renders/shot_002.mp4", "kling", {"duration": 3}),
        ],
        export_output_path="output/exports/chapter_001.mp4",
    )
    return plan.as_dict()

