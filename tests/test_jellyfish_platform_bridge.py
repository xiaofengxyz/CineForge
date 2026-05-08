from src.film_engine import (
    JELLYFISH_FILM_WORKFLOW,
    CompiledPrompt,
    EntityRegistry,
    StudioAsset,
    StudioChapter,
    StudioPlatformBridge,
    StudioProject,
    StudioShot,
)


def test_register_assets_maps_jellyfish_assets_to_ecs_entities():
    bridge = StudioPlatformBridge()
    registry = EntityRegistry()
    asset = StudioAsset(
        id="char_001",
        kind="character",
        name="Ari",
        description="Lead character",
        reference_media=["ref/ari_front.png"],
        metadata={"voice_id": "voice_ari"},
    )

    entities = bridge.register_assets(registry, [asset])

    assert entities[0].id == "char_001"
    assert registry.get("char_001") is entities[0]
    assert entities[0].get_component("identity").data["name"] == "Ari"
    assert entities[0].get_component("references").data["media"] == ["ref/ari_front.png"]
    assert entities[0].get_component("metadata").data["voice_id"] == "voice_ari"


def test_shot_to_continuity_merges_asset_references_and_state():
    bridge = StudioPlatformBridge()
    assets = [
        StudioAsset(
            id="char_001",
            kind="character",
            name="Ari",
            reference_media=["ref/ari_front.png"],
        ),
        StudioAsset(
            id="scene_001",
            kind="scene",
            name="Neon alley",
            reference_media=["ref/alley.png"],
            metadata={"lighting": "neon_rain"},
        ),
        StudioAsset(
            id="prop_001",
            kind="prop",
            name="Envelope",
            reference_media=["ref/envelope.png"],
        ),
    ]
    shot = StudioShot(
        id="shot_001",
        project_id="project_001",
        chapter_id="chapter_001",
        index=7,
        scene_id="scene_001",
        character_ids=["char_001"],
        prop_ids=["prop_001"],
        reference_media=["shots/shot_001_keyframe.png"],
        metadata={
            "outfit_map": {"char_001": "coat_black"},
            "emotion_map": {"char_001": "wary"},
        },
    )

    continuity = bridge.shot_to_continuity(shot, assets=assets)

    assert continuity.shot_id == "shot_001"
    assert continuity.character_ids == ["char_001"]
    assert continuity.scene_id == "scene_001"
    assert continuity.lighting == "neon_rain"
    assert continuity.outfit_map == {"char_001": "coat_black"}
    assert continuity.emotion_map == {"char_001": "wary"}
    assert continuity.timeline_position == "chapter:chapter_001:shot:0007"
    assert continuity.reference_media == [
        "shots/shot_001_keyframe.png",
        "ref/ari_front.png",
        "ref/envelope.png",
        "ref/alley.png",
    ]


def test_build_chapter_workflow_preserves_platform_to_film_core_order():
    bridge = StudioPlatformBridge()
    project = StudioProject(id="project_001", title="Pilot")
    chapter = StudioChapter(
        id="chapter_001",
        project_id=project.id,
        title="Episode 1",
        shot_ids=["shot_001", "shot_002"],
    )
    shots = [
        StudioShot(
            id="shot_001",
            project_id=project.id,
            chapter_id=chapter.id,
            index=1,
        ),
        StudioShot(
            id="shot_002",
            project_id=project.id,
            chapter_id=chapter.id,
            index=2,
        ),
    ]

    graph = bridge.build_chapter_workflow(project, chapter, shots)
    ordered = graph.topological_order()

    assert [node.system for node in ordered] == JELLYFISH_FILM_WORKFLOW
    assert ordered[0].payload["project_id"] == project.id
    assert ordered[0].payload["chapter_id"] == chapter.id
    assert ordered[0].payload["shot_ids"] == ["shot_001", "shot_002"]


def test_compile_render_request_keeps_runtime_provider_at_boundary():
    bridge = StudioPlatformBridge()
    shot = StudioShot(
        id="shot_001",
        project_id="project_001",
        chapter_id="chapter_001",
        index=1,
    )
    compiled = CompiledPrompt(
        provider="kling",
        text="shot=shot_001; movement=dolly_in",
        negative_text="identity drift",
        references=["ref/ari_front.png"],
        parameters={"camera": "dolly_in"},
    )

    request = bridge.compile_render_request(
        shot,
        compiled,
        model="kling-v1",
        output_path="output/shot_001.mp4",
    )

    assert request.shot_id == "shot_001"
    assert request.prompt == "shot=shot_001; movement=dolly_in"
    assert request.model == "kling-v1"
    assert request.references == ["ref/ari_front.png"]
    assert request.parameters["provider"] == "kling"
    assert request.parameters["negative_prompt"] == "identity drift"
