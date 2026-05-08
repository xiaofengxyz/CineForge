from src.film_engine import JellyfishRecordMapper, JellyfishShotBundle


def test_maps_jellyfish_project_and_chapter_records():
    mapper = JellyfishRecordMapper()

    project = mapper.project(
        {
            "id": "project_001",
            "name": "Neon Trial",
            "description": "A short drama pilot",
            "style": "真人都市",
            "visual_style": "现实",
            "seed": 4102,
            "default_video_ratio": "9:16",
            "chapters": [{"id": "chapter_001"}, {"id": "chapter_002"}],
        }
    )
    chapter = mapper.chapter(
        {
            "id": "chapter_001",
            "project_id": "project_001",
            "index": 3,
            "title": "Rain Alley",
            "raw_text": "Chapter text",
            "condensed_text": "Condensed text",
            "status": "shooting",
            "shots": ["shot_001", {"id": "shot_002"}],
        }
    )

    assert project.id == "project_001"
    assert project.title == "Neon Trial"
    assert project.chapter_ids == ["chapter_001", "chapter_002"]
    assert project.metadata["seed"] == 4102
    assert project.metadata["default_video_ratio"] == "9:16"
    assert chapter.project_id == project.id
    assert chapter.order == 3
    assert chapter.shot_ids == ["shot_001", "shot_002"]
    assert chapter.metadata["status"] == "shooting"


def test_maps_jellyfish_asset_records_with_reference_images():
    mapper = JellyfishRecordMapper()

    asset = mapper.asset(
        {
            "id": "scene_001",
            "type": "scene",
            "name": "Neon alley",
            "description": "Rainy narrow alley",
            "tags": ["rain", "night"],
            "thumbnail": "files/thumb_scene",
            "images": [
                {"file_id": "files/scene_front", "quality_level": "HIGH"},
                {"file_id": "files/scene_detail"},
            ],
            "visual_style": "现实",
        }
    )

    assert asset.kind == "scene"
    assert asset.reference_media == [
        "files/thumb_scene",
        "files/scene_front",
        "files/scene_detail",
    ]
    assert asset.metadata["tags"] == ["rain", "night"]
    assert asset.metadata["visual_style"] == "现实"


def test_maps_jellyfish_shot_bundle_to_generation_ready_studio_shot():
    mapper = JellyfishRecordMapper()
    bundle = JellyfishShotBundle(
        project={"id": "project_001", "name": "Neon Trial"},
        chapter={"id": "chapter_001", "project_id": "project_001", "title": "Rain Alley"},
        shot={
            "id": "shot_001",
            "chapter_id": "chapter_001",
            "index": 4,
            "title": "The envelope changes hands",
            "status": "ready",
            "script_excerpt": "She hides the envelope under her coat.",
            "thumbnail": "files/shot_thumb",
            "generated_video_file_id": "files/generated_video",
            "extraction": {"state": "extracted_resolved"},
        },
        detail={
            "camera_shot": "CU",
            "angle": "LOW_ANGLE",
            "movement": "DOLLY_IN",
            "scene_id": "scene_001",
            "duration": 5,
            "override_video_ratio": "9:16",
            "mood_tags": ["tense", "secretive"],
            "atmosphere": "neon rain",
            "action_beats": ["hand reaches", "envelope disappears"],
        },
        asset_overview=[
            {
                "type": "character",
                "linked_entity_id": "char_001",
                "name": "Ari",
                "is_linked": True,
            },
            {
                "type": "prop",
                "linked_entity_id": "prop_001",
                "name": "Envelope",
                "is_linked": True,
            },
            {
                "type": "costume",
                "linked_entity_id": "costume_001",
                "name": "Black coat",
                "is_linked": True,
            },
        ],
        dialogue_lines=[
            {"index": 2, "text": "No one can see this."},
            {"index": 1, "text": "Keep walking."},
        ],
        frame_images=[
            {"frame_type": "first", "file_id": "files/first_frame"},
            {"frame_type": "key", "file_id": "files/key_frame"},
        ],
    )

    shot = mapper.shot_bundle(bundle)

    assert shot.id == "shot_001"
    assert shot.project_id == "project_001"
    assert shot.chapter_id == "chapter_001"
    assert shot.is_generation_ready is True
    assert shot.summary == "She hides the envelope under her coat."
    assert shot.scene_id == "scene_001"
    assert shot.character_ids == ["char_001"]
    assert shot.prop_ids == ["prop_001"]
    assert shot.costume_ids == ["costume_001"]
    assert shot.dialogue == ["Keep walking.", "No one can see this."]
    assert shot.camera["framing"] == "CU"
    assert shot.camera["movement"] == "DOLLY_IN"
    assert shot.camera["emotion"] == ["tense", "secretive"]
    assert shot.camera["ratio"] == "9:16"
    assert shot.duration == 5.0
    assert shot.reference_media == [
        "files/shot_thumb",
        "files/generated_video",
        "files/first_frame",
        "files/key_frame",
    ]
    assert shot.metadata["jellyfish_status"] == "ready"
    assert shot.metadata["extraction"] == {"state": "extracted_resolved"}


def test_maps_jellyfish_task_records_without_coupling_to_task_manager():
    mapper = JellyfishRecordMapper()

    task = mapper.task(
        {
            "task_id": "task_001",
            "task_kind": "video_generation",
            "status": "running",
            "progress": 45,
            "relation_type": "shot",
            "relation_entity_id": "shot_001",
            "resource_type": "video",
            "result": {"file_id": "files/video_001"},
        },
        project_id="project_001",
    )

    assert task.id == "task_001"
    assert task.project_id == "project_001"
    assert task.shot_id == "shot_001"
    assert task.task_type == "video_generation"
    assert task.status == "running"
    assert task.result_media == ["files/video_001"]
    assert task.metadata["progress"] == 45
