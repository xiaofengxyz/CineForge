from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class WorkflowPromptStage:
    """Executable stage mirrored from docs/Codex_Workflow_Prompts."""

    id: str
    title: str
    prompt_file: str
    goal: str


CINEFORGE_PROMPT_WORKFLOW: tuple[WorkflowPromptStage, ...] = (
    WorkflowPromptStage(
        id="workflow_architecture",
        title="Workflow Architecture",
        prompt_file="01_WORKFLOW_ARCHITECTURE_PROMPT.md",
        goal="Create the graph-first production workflow and persistence envelope.",
    ),
    WorkflowPromptStage(
        id="novel_engine",
        title="Novel Engine",
        prompt_file="02_STAGE1_NOVEL_ENGINE_PROMPT.md",
        goal="Generate world bible, relationship graph, outline, prose, and cliffhangers.",
    ),
    WorkflowPromptStage(
        id="asset_pipeline",
        title="Drama Asset Pipeline",
        prompt_file="03_STAGE2_ASSET_PIPELINE_PROMPT.md",
        goal="Build character bible, scene bible, shot graph, and storyboard plan.",
    ),
    WorkflowPromptStage(
        id="image_runtime",
        title="Image Runtime",
        prompt_file="04_STAGE3_IMAGE_RUNTIME_PROMPT.md",
        goal="Prepare provider-neutral image model calls for references and storyboards.",
    ),
    WorkflowPromptStage(
        id="video_runtime",
        title="Video Runtime",
        prompt_file="05_STAGE4_VIDEO_RUNTIME_PROMPT.md",
        goal="Prepare provider-neutral video render requests for each shot.",
    ),
    WorkflowPromptStage(
        id="qa_retry_engine",
        title="QA Retry Engine",
        prompt_file="06_QA_RETRY_ENGINE_PROMPT.md",
        goal="Evaluate generated evidence and build deterministic retry requests.",
    ),
    WorkflowPromptStage(
        id="studio_ui",
        title="Studio UI",
        prompt_file="07_STUDIO_UI_PROMPT.md",
        goal="Expose workflow controls, evidence, and next actions to Studio surfaces.",
    ),
    WorkflowPromptStage(
        id="data_schema",
        title="Data Schema",
        prompt_file="08_DATA_SCHEMA_PROMPT.md",
        goal="Persist schemas for workflow, assets, runtime requests, QA, and retry.",
    ),
    WorkflowPromptStage(
        id="final_integration",
        title="Final Integration",
        prompt_file="09_FINAL_INTEGRATION_PROMPT.md",
        goal="Connect all stages into an executable AI drama operating system.",
    ),
)


@dataclass(frozen=True)
class StageSwitch:
    """Execution switch for one workflow prompt stage."""

    stage_id: str
    enabled: bool = True
    automatic: bool = True
    note: str = ""

    @classmethod
    def from_value(cls, stage_id: str, value: Any) -> "StageSwitch":
        """Accept compact booleans or full dicts from API/JSON config."""
        if isinstance(value, bool):
            return cls(stage_id=stage_id, enabled=True, automatic=value)
        if isinstance(value, dict):
            return cls(
                stage_id=stage_id,
                enabled=bool(value.get("enabled", True)),
                automatic=bool(value.get("automatic", value.get("auto", True))),
                note=str(value.get("note") or ""),
            )
        return cls(stage_id=stage_id)


@dataclass(frozen=True)
class StageExecutionRecord:
    """Serializable progress record for one workflow prompt stage."""

    stage_id: str
    title: str
    status: str
    enabled: bool
    automatic: bool
    evidence: str = ""
    prompt_file: str = ""
    goal: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Return a stable record for API responses and persisted state."""
        return {
            "stage_id": self.stage_id,
            "title": self.title,
            "status": self.status,
            "enabled": self.enabled,
            "automatic": self.automatic,
            "evidence": self.evidence,
            "prompt_file": self.prompt_file,
            "goal": self.goal,
        }


@dataclass(frozen=True)
class WorkflowControlConfig:
    """Switch set controlling automatic or manual stage progression."""

    switches: dict[str, StageSwitch] = field(default_factory=dict)

    @classmethod
    def automatic(cls) -> "WorkflowControlConfig":
        """Create a config where every stage runs through without review stops."""
        return cls()

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "WorkflowControlConfig":
        """Build stage switches from a user/API mapping."""
        raw = value or {}
        return cls(
            switches={
                stage_id: StageSwitch.from_value(stage_id, switch_value)
                for stage_id, switch_value in raw.items()
            }
        )

    def switch_for(self, stage_id: str) -> StageSwitch:
        """Return an explicit switch or the default automatic switch."""
        return self.switches.get(stage_id, StageSwitch(stage_id=stage_id))

    def as_dict(self, stages: tuple[WorkflowPromptStage, ...] = CINEFORGE_PROMPT_WORKFLOW) -> dict[str, Any]:
        """Serialize controls in stage order so UI can render toggles predictably."""
        return {
            stage.id: {
                "enabled": self.switch_for(stage.id).enabled,
                "automatic": self.switch_for(stage.id).automatic,
                "note": self.switch_for(stage.id).note,
            }
            for stage in stages
        }


@dataclass(frozen=True)
class WorkflowExecutionState:
    """Final execution state after a controlled workflow pass."""

    records: list[StageExecutionRecord]
    waiting_for_user: bool = False
    halted_stage_id: str | None = None
    next_stage_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a compact progress index for clients and saved state."""
        return {
            "waiting_for_user": self.waiting_for_user,
            "halted_stage_id": self.halted_stage_id,
            "next_stage_id": self.next_stage_id,
            "done_count": sum(1 for record in self.records if record.status == "done"),
            "waiting_count": sum(1 for record in self.records if record.status == "waiting_for_user"),
            "blocked_count": sum(1 for record in self.records if record.status == "blocked"),
            "records": [record.as_dict() for record in self.records],
        }


class WorkflowStageGate:
    """Stateful gate that stops after the first non-automatic completed stage."""

    def __init__(
        self,
        *,
        config: WorkflowControlConfig | None = None,
        stages: tuple[WorkflowPromptStage, ...] = CINEFORGE_PROMPT_WORKFLOW,
    ) -> None:
        self.config = config or WorkflowControlConfig.automatic()
        self.stages = stages
        self._records: dict[str, StageExecutionRecord] = {}
        self._halted_stage_id: str | None = None
        self._next_stage_id: str | None = None

    @property
    def halted(self) -> bool:
        """Tell callers whether downstream automatic execution must stop."""
        return self._halted_stage_id is not None

    def should_run(self, stage_id: str) -> bool:
        """Return true only when a stage is enabled and no manual gate stopped."""
        switch = self.config.switch_for(stage_id)
        if self.halted or not switch.enabled:
            return False
        return True

    def complete(self, stage_id: str, *, evidence: str) -> None:
        """Record a completed stage and halt if it requires user review."""
        stage = self._stage(stage_id)
        switch = self.config.switch_for(stage_id)
        status = "done" if switch.automatic else "waiting_for_user"
        self._records[stage_id] = StageExecutionRecord(
            stage_id=stage.id,
            title=stage.title,
            status=status,
            enabled=switch.enabled,
            automatic=switch.automatic,
            evidence=evidence,
            prompt_file=stage.prompt_file,
            goal=stage.goal,
        )
        if not switch.automatic:
            self._halted_stage_id = stage_id
            self._next_stage_id = self._find_next_enabled_stage(stage_id)

    def finalize(self) -> WorkflowExecutionState:
        """Fill in skipped/blocked records so progress is fully recoverable."""
        records: list[StageExecutionRecord] = []
        for stage in self.stages:
            if stage.id in self._records:
                records.append(self._records[stage.id])
                continue
            switch = self.config.switch_for(stage.id)
            status = "disabled" if not switch.enabled else "blocked" if self.halted else "pending"
            records.append(
                StageExecutionRecord(
                    stage_id=stage.id,
                    title=stage.title,
                    status=status,
                    enabled=switch.enabled,
                    automatic=switch.automatic,
                    evidence="Waiting for manual approval upstream." if status == "blocked" else "",
                    prompt_file=stage.prompt_file,
                    goal=stage.goal,
                )
            )
        return WorkflowExecutionState(
            records=records,
            waiting_for_user=self.halted,
            halted_stage_id=self._halted_stage_id,
            next_stage_id=self._next_stage_id,
        )

    def _stage(self, stage_id: str) -> WorkflowPromptStage:
        for stage in self.stages:
            if stage.id == stage_id:
                return stage
        raise KeyError(f"Unknown workflow prompt stage: {stage_id}")

    def _find_next_enabled_stage(self, stage_id: str) -> str | None:
        seen_current = False
        for stage in self.stages:
            if seen_current and self.config.switch_for(stage.id).enabled:
                return stage.id
            if stage.id == stage_id:
                seen_current = True
        return None

