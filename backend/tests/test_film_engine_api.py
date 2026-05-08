from __future__ import annotations

from fastapi.testclient import TestClient


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
    assert stages[0]["owner"] == "Jellyfish"
    assert stages[-1]["id"] == "final_export"
    assert stages[-1]["status"] == "done"

