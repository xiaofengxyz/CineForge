from __future__ import annotations

from pathlib import Path

from src.film_engine.jellyfish_base import inspect_jellyfish_base
from src.film_engine.studio import build_industrial_review, build_stage_index


def test_inspect_jellyfish_base_accepts_api_shape_without_git_checkout(tmp_path: Path):
    base = tmp_path / "jellyfish"
    (base / "deploy" / "compose").mkdir(parents=True)
    (base / "backend").mkdir()
    (base / "front").mkdir()
    (base / "site").mkdir()
    (base / "deploy" / "compose" / "docker-compose.yml").write_text("services: {}\n")
    (base / "deploy" / "compose" / ".env.example").write_text("MYSQL_PORT=3306\n")
    (base / "backend" / "pyproject.toml").write_text("[project]\nname='jellyfish'\n")
    (base / "front" / "package.json").write_text('{"name":"jellyfish"}\n')

    status = inspect_jellyfish_base(base)
    payload = status.as_dict()

    assert payload["available"] is True
    assert payload["compose_ready"] is True
    assert payload["upstream_url"] == "https://github.com/Forget-C/Jellyfish"
    assert payload["missing"] == []
    assert payload["run_commands"][0]["id"] == "docker_compose"
    assert "7788" in payload["run_commands"][0]["ports"]["frontend"]


def test_stage_index_uses_artifacts_as_completion_evidence():
    summary = {
        "project": {"id": "p1", "title": "Project"},
        "chapter": {"id": "c1", "title": "Chapter"},
        "workflow": [
            "script_breakdown",
            "shot_preparation",
            "asset_consistency",
            "film_state",
            "prompt_compiler",
            "runtime_adapter",
            "qa_engine",
            "retry_engine",
            "final_export",
        ],
        "metadata": {"shot_count": 1, "retry_count": 1},
        "render_requests": [
            {
                "model": "kling",
                "prompt": "shot=s1; framing=MS; movement=DOLLY_IN; lens=35mm; emotion=tense; lighting=neon; mood=suspense; outfits=char:coat",
                "references": ["ref.png"],
                "parameters": {
                    "negative_prompt": "wrong face",
                    "continuity": {
                        "outfit_map": {"char": "coat"},
                        "emotion_map": {"char": "tense"},
                        "lighting": "neon",
                    },
                },
            }
        ],
        "retry_requests": [{"shot_id": "s1"}],
        "qa": {
            "passed": False,
            "reports": [
                {
                    "shot_id": "s1",
                    "passed": False,
                    "score": 0.5,
                    "issues": [{"code": "low_face_similarity"}],
                }
            ],
        },
        "post_production": {"enabled": True},
    }

    stages = build_stage_index(summary)

    assert [stage.status for stage in stages] == ["done"] * 9
    assert stages[0].owner == "Runtime"
    assert stages[-1].id == "film_state_engine"
    assert stages[-1].evidence == "Continuity parameters travel with every compiled render request."


def test_industrial_review_marks_base_blocked_when_jellyfish_missing(tmp_path: Path):
    status = inspect_jellyfish_base(tmp_path / "missing")
    review = build_industrial_review(status)

    assert review[0].reference == "Jellyfish"
    assert review[0].status == "blocked"
    assert any(item.pain_point == "Prompt randomness" for item in review)
