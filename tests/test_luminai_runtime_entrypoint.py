from __future__ import annotations

import json
import threading
from urllib.request import urlopen

from src.film_engine.demo import build_demo_plan_summary
from src.film_engine.server import create_server


def _get_json(url: str) -> dict[str, object]:
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_text(url: str) -> str:
    with urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def test_demo_plan_summary_exposes_closed_loop_production_contract():
    summary = build_demo_plan_summary()

    assert summary["metadata"]["mode"] == "closed_loop_industrial_batch"
    assert summary["metadata"]["retry_count"] == 1
    assert summary["qa"]["passed"] is False
    assert summary["workflow"] == [
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
    assert len(summary["render_requests"]) == 2
    assert len(summary["retry_requests"]) == 1
    retry = summary["retry_requests"][0]
    assert retry["parameters"]["reference_strength"] == "high"
    assert retry["parameters"]["retry_attempt"] == 2
    assert summary["post_production"]["enabled"] is True

    json.dumps(summary, sort_keys=True)


def test_http_server_serves_health_and_closed_loop_demo_plan():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    base_url = f"http://{host}:{port}"
    try:
        health = _get_json(f"{base_url}/health")
        demo = _get_json(f"{base_url}/demo/closed-loop-plan")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert health["status"] == "ok"
    assert health["engine"] == "LuminAI"
    assert "prompt_compiler" in health["workflow"]
    assert demo["project"]["title"] == "Neon Trial"
    assert demo["metadata"]["retry_count"] == 1


def test_http_server_serves_operable_studio_dashboard_and_status_apis():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    base_url = f"http://{host}:{port}"
    try:
        dashboard = _get_text(f"{base_url}/")
        studio = _get_json(f"{base_url}/api/studio/status")
        jellyfish = _get_json(f"{base_url}/api/jellyfish/base-status")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    assert "LuminAI Studio Dashboard" in dashboard
    assert "Stage Index" in dashboard
    assert "Shot Workbench" in dashboard
    assert studio["summary"]["project"]["title"] == "Neon Trial"
    assert studio["stages"][0]["id"] == "script_breakdown"
    assert any(stage["id"] == "final_export" for stage in studio["stages"])
    assert jellyfish["upstream_url"] == "https://github.com/Forget-C/Jellyfish"
