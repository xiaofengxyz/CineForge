from src.film_engine import CINEFORGE_PROMPT_WORKFLOW, WorkflowControlConfig, WorkflowStageGate


def test_workflow_stage_gate_stops_after_non_automatic_stage():
    controls = WorkflowControlConfig.from_mapping(
        {"novel_engine": {"enabled": True, "automatic": False}}
    )
    gate = WorkflowStageGate(config=controls)

    for stage in CINEFORGE_PROMPT_WORKFLOW:
        if not gate.should_run(stage.id):
            continue
        gate.complete(stage.id, evidence=f"{stage.id} completed")
        if gate.halted:
            break

    state = gate.finalize()
    records = {record.stage_id: record for record in state.records}

    assert state.waiting_for_user is True
    assert state.halted_stage_id == "novel_engine"
    assert state.next_stage_id == "asset_pipeline"
    assert records["workflow_architecture"].status == "done"
    assert records["novel_engine"].status == "waiting_for_user"
    assert records["asset_pipeline"].status == "blocked"


def test_workflow_stage_gate_marks_disabled_stage_and_keeps_automatic_progression():
    controls = WorkflowControlConfig.from_mapping(
        {"asset_pipeline": {"enabled": False, "automatic": True}}
    )
    gate = WorkflowStageGate(config=controls)

    for stage in CINEFORGE_PROMPT_WORKFLOW[:4]:
        if not gate.should_run(stage.id):
            continue
        gate.complete(stage.id, evidence=f"{stage.id} completed")

    state = gate.finalize()
    records = {record.stage_id: record for record in state.records}

    assert state.waiting_for_user is False
    assert records["asset_pipeline"].status == "disabled"
    assert records["image_runtime"].status == "done"

