from src.film_engine import (
    CharacterBible,
    DirectorConsistencyEngine,
    DirectorRuleEngine,
    PromptCompiler,
    SceneBible,
    ShotContinuityState,
    StudioShot,
)


def test_director_consistency_merges_character_and_scene_bibles_into_prompt_context():
    shot = StudioShot(
        id="shot_001",
        project_id="project_001",
        chapter_id="chapter_001",
        index=1,
        summary="Ari stops under the sign.",
        scene_id="scene_001",
        character_ids=["char_001"],
        camera={
            "framing": "medium_closeup",
            "movement": "dolly_in",
            "lens": "85mm",
            "emotion": "wary",
            "pacing": "slow",
        },
        duration=4,
    )
    continuity = ShotContinuityState(
        shot_id=shot.id,
        character_ids=["char_001"],
        scene_id="scene_001",
        reference_media=["shots/shot_001_key.png"],
    )
    character = CharacterBible(
        id="char_001",
        name="Ari",
        reference_media=["refs/ari_front.png"],
        outfits={"coat_black": "black rain coat"},
        default_outfit="coat_black",
        voice_id="voice_ari",
        lora="ari_v12.safetensors",
        embeddings=["ari_face_v4"],
        identity_terms=["sharp bob haircut"],
        negative_terms=["wrong face"],
    )
    scene = SceneBible(
        id="scene_001",
        name="Neon alley",
        location="rainy alley",
        lighting="neon_blue",
        weather="rain",
        tone="noir",
        mood="suspense",
        camera_style="handheld restrained",
        reference_media=["refs/alley.png"],
    )

    prepared = DirectorConsistencyEngine().prepare_shot(
        shot=shot,
        continuity=continuity,
        character_bibles=[character],
        scene_bibles=[scene],
    )
    compiled = PromptCompiler().compile_shot(
        provider="kling",
        director_dsl=prepared.director_dsl,
        continuity=prepared.continuity,
    )

    assert prepared.passed is True
    assert prepared.continuity.outfit_map == {"char_001": "black rain coat"}
    assert prepared.continuity.emotion_map == {"char_001": "wary"}
    assert prepared.continuity.lighting == "neon_blue"
    assert prepared.continuity.reference_media == [
        "shots/shot_001_key.png",
        "refs/ari_front.png",
        "refs/alley.png",
    ]
    assert prepared.director_dsl["voice_map"] == {"char_001": "voice_ari"}
    assert prepared.director_dsl["character_context"]["char_001"]["lora"] == "ari_v12.safetensors"
    assert prepared.director_dsl["scene_mood"] == "suspense"
    assert "lens=85mm" in compiled.text
    assert "outfits=char_001:black rain coat" in compiled.text
    assert "wrong face" in compiled.negative_text
    assert compiled.parameters["voice_map"] == {"char_001": "voice_ari"}


def test_director_rules_report_missing_dsl_fields_and_invalid_duration():
    result = DirectorRuleEngine().validate_dsl(
        {
            "framing": "wide",
            "movement": "static",
            "duration": 0,
        }
    )

    assert result.passed is False
    assert [issue.code for issue in result.issues] == [
        "missing_lens",
        "missing_emotion",
        "invalid_duration",
    ]
    assert result.issues[-1].severity == "high"


def test_missing_bibles_block_generation_context():
    shot = StudioShot(
        id="shot_001",
        project_id="project_001",
        chapter_id="chapter_001",
        index=1,
        scene_id="scene_001",
        character_ids=["char_001"],
        camera={
            "framing": "wide",
            "movement": "track",
            "lens": "35mm",
            "emotion": "tense",
        },
        duration=3,
    )
    continuity = ShotContinuityState(
        shot_id=shot.id,
        character_ids=["char_001"],
        scene_id="scene_001",
    )

    prepared = DirectorConsistencyEngine().prepare_shot(
        shot=shot,
        continuity=continuity,
        character_bibles=[],
        scene_bibles=[],
    )

    assert prepared.passed is False
    assert [issue.code for issue in prepared.issues] == [
        "missing_character_bible",
        "missing_scene_bible",
    ]
    assert all(issue.severity == "high" for issue in prepared.issues)
