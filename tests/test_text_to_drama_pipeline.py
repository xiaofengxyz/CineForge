import json
from pathlib import Path

from src.film_engine import TextToDramaConfig, TextToDramaPipeline, load_text_to_drama_state


def test_text_to_drama_pipeline_generates_novel_assets_runtime_and_state(tmp_path):
    config = TextToDramaConfig.from_mapping(
        {
            "title": "Neon Trial",
            "run_id": "unit_run",
            "output_dir": str(tmp_path),
            "max_chapters": 2,
            "shots_per_chapter": 2,
            "runtime_profiles": {
                "text": {"provider": "deterministic", "model": "planner"},
                "image": {"provider": "deterministic", "model": "storyboard"},
                "video": {
                    "provider": "kling",
                    "model": "kling-v1",
                    "base_url": "https://video.example",
                    "api_key": "secret-token",
                },
            },
        }
    )

    result = TextToDramaPipeline().run(
        "Ari finds a key in a neon alley. Ari follows the signal into the night.",
        config=config,
    )

    artifacts = result["artifacts"]
    state_path = Path(result["state_path"])

    assert result["status"] == "completed"
    assert state_path.exists()
    assert len(artifacts["novel_plan"]["chapters"]) == 2
    assert len(artifacts["asset_bundle"]["character_bibles"]) >= 1
    assert artifacts["image_runtime"]
    assert artifacts["video_plans"]
    assert artifacts["video_plans"][0]["render_requests"]
    assert artifacts["qa_retry"]["qa_report_count"] > 0
    assert artifacts["final_integration"]["ready_for_batch_submission"] is True
    assert "secret-token" not in json.dumps(result)

    restored = load_text_to_drama_state(state_path)
    assert restored["run_id"] == "unit_run"
    assert restored["status"] == "completed"


def test_text_to_drama_pipeline_waits_after_manual_stage(tmp_path):
    config = TextToDramaConfig.from_mapping(
        {
            "title": "Manual Novel Review",
            "run_id": "manual_run",
            "output_dir": str(tmp_path),
            "stage_switches": {"novel_engine": {"enabled": True, "automatic": False}},
        }
    )

    result = TextToDramaPipeline().run(
        "A pilot discovers an impossible city above the ocean.",
        config=config,
    )
    records = {
        record["stage_id"]: record
        for record in result["workflow_control"]["records"]
    }

    assert result["status"] == "waiting_for_user"
    assert result["workflow_control"]["halted_stage_id"] == "novel_engine"
    assert records["novel_engine"]["status"] == "waiting_for_user"
    assert records["asset_pipeline"]["status"] == "blocked"
    assert result["artifacts"]["novel_plan"]["chapters"]
    assert result["artifacts"]["asset_bundle"] is None
    assert result["artifacts"]["video_plans"] == []

