from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import JELLYFISH_FILM_WORKFLOW
from .jellyfish_base import JellyfishBaseStatus


@dataclass(frozen=True)
class StageDefinition:
    id: str
    title: str
    owner: str
    goal: str
    artifacts: tuple[str, ...]
    ui_surface: str


@dataclass
class StageEvidence:
    id: str
    title: str
    owner: str
    status: str
    evidence: str
    goal: str = ""
    artifacts: list[str] | None = None
    ui_surface: str = ""
    metrics: dict[str, Any] | None = None


@dataclass
class IndustrialReviewItem:
    reference: str
    status: str
    pain_point: str
    recommendation: str


ENGINE_STAGE_DEFINITIONS: tuple[StageDefinition, ...] = (
    StageDefinition(
        id="runtime_adapter",
        title="Runtime Adapter",
        owner="Runtime",
        goal="Route image/video generation through provider-neutral render requests.",
        artifacts=("src/models/*", "src/utils/provider_registry.py", "src/film_engine/platform.py"),
        ui_surface="/film-engine",
    ),
    StageDefinition(
        id="director_dsl",
        title="Director DSL",
        owner="Director System",
        goal="Compile framing, movement, lens, emotion, pacing, and dialogue into structured shot intent.",
        artifacts=("src/film_engine/core.py::DirectorConsistencyEngine", "samples/director_dsl/*"),
        ui_surface="/film-engine",
    ),
    StageDefinition(
        id="shot_graph",
        title="Shot Graph",
        owner="Graph Workflow",
        goal="Keep chapter production ordered as explicit graph nodes with deterministic dependencies.",
        artifacts=("src/film_engine/core.py::WorkflowGraph", "samples/shot_graph/*"),
        ui_surface="/film-engine",
    ),
    StageDefinition(
        id="prompt_compiler",
        title="Prompt Compiler",
        owner="Prompt System",
        goal="Build prompts from structured continuity state instead of ad hoc hardcoded prose.",
        artifacts=("src/film_engine/core.py::PromptCompiler", "samples/prompt_compiler/*"),
        ui_surface="/film-engine",
    ),
    StageDefinition(
        id="character_registry",
        title="Character Registry",
        owner="Consistency System",
        goal="Resolve character identity, outfit, voice, reference media, embeddings, LoRA, and negatives.",
        artifacts=("src/film_engine/core.py::CharacterBible", "samples/character_registry/*"),
        ui_surface="/film-engine",
    ),
    StageDefinition(
        id="scene_registry",
        title="Scene Registry",
        owner="Consistency System",
        goal="Resolve scene lighting, weather, tone, mood, camera style, and reference media per shot.",
        artifacts=("src/film_engine/core.py::SceneBible", "samples/scene_registry/*"),
        ui_surface="/film-engine",
    ),
    StageDefinition(
        id="qa_engine",
        title="QA Engine",
        owner="QA",
        goal="Score rendered shots with structured metrics and machine-actionable issue codes.",
        artifacts=("src/film_engine/core.py::QAEngine", "samples/qa_engine/*"),
        ui_surface="/film-engine",
    ),
    StageDefinition(
        id="retry_engine",
        title="Retry Engine",
        owner="QA",
        goal="Convert QA failures into deterministic repair prompts and retry parameters.",
        artifacts=("src/film_engine/core.py::RetryEngine", "samples/retry_engine/*"),
        ui_surface="/film-engine",
    ),
    StageDefinition(
        id="film_state_engine",
        title="Film State Engine",
        owner="Film Core",
        goal="Persist shot continuity for characters, wardrobe, emotion, lighting, timeline, and references.",
        artifacts=("src/film_engine/core.py::ShotContinuityState", "samples/film_state_engine/*"),
        ui_surface="/film-engine",
    ),
)


WORKFLOW_STAGE_TITLES: dict[str, tuple[str, str]] = {
    "script_breakdown": ("Script Breakdown", "Jellyfish"),
    "shot_preparation": ("Shot Preparation", "Jellyfish"),
    "asset_consistency": ("Asset Consistency", "Jellyfish"),
    "film_state": ("Film State", "Film Core"),
    "prompt_compiler": ("Prompt Compiler", "Prompt System"),
    "runtime_adapter": ("Runtime Adapter", "Runtime"),
    "qa_engine": ("QA Engine", "QA"),
    "retry_engine": ("Retry Engine", "QA"),
    "final_export": ("Final Export", "Post"),
}


def _render_requests(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in summary.get("render_requests") or [] if isinstance(item, dict)]


def _retry_requests(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in summary.get("retry_requests") or [] if isinstance(item, dict)]


def _qa_reports(summary: dict[str, Any]) -> list[dict[str, Any]]:
    qa = summary.get("qa") or {}
    if not isinstance(qa, dict):
        return []
    return [item for item in qa.get("reports") or [] if isinstance(item, dict)]


def _has_continuity_parameters(render_requests: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(item.get("parameters"), dict)
        and isinstance(item["parameters"].get("continuity"), dict)
        for item in render_requests
    )


def _has_prompt_tokens(render_requests: list[dict[str, Any]], tokens: tuple[str, ...]) -> bool:
    prompts = [str(item.get("prompt") or "") for item in render_requests]
    return bool(prompts) and all(any(token in prompt for prompt in prompts) for token in tokens)


def _stage_status(condition: bool) -> str:
    return "done" if condition else "pending"


def build_stage_index(summary: dict[str, Any]) -> list[StageEvidence]:
    """Return the canonical nine industrial Film Engine capability stages."""

    workflow = list(summary.get("workflow") or JELLYFISH_FILM_WORKFLOW)
    render_requests = _render_requests(summary)
    retry_requests = _retry_requests(summary)
    qa_reports = _qa_reports(summary)
    qa = summary.get("qa") if isinstance(summary.get("qa"), dict) else {}

    evidence_by_stage: dict[str, tuple[bool, str, dict[str, Any]]] = {
        "runtime_adapter": (
            bool(render_requests),
            f"Provider-neutral render requests={len(render_requests)}.",
            {"render_requests": len(render_requests)},
        ),
        "director_dsl": (
            _has_prompt_tokens(render_requests, ("framing=", "movement=", "lens=", "emotion=")),
            "Render prompts include framing, movement, lens, and emotion DSL tokens.",
            {"compiled_shots": len(render_requests)},
        ),
        "shot_graph": (
            len(workflow) >= 9,
            f"Workflow graph nodes={len(workflow)}.",
            {"workflow_nodes": len(workflow)},
        ),
        "prompt_compiler": (
            bool(render_requests) and all(str(item.get("prompt") or "") for item in render_requests),
            f"Compiled prompts={len(render_requests)}.",
            {"compiled_prompts": len(render_requests)},
        ),
        "character_registry": (
            any(item.get("references") for item in render_requests)
            and any(
                isinstance(item.get("parameters"), dict)
                and str(item["parameters"].get("negative_prompt") or "")
                for item in render_requests
            ),
            "Character references and negative identity terms are attached to render requests.",
            {"referenced_shots": sum(1 for item in render_requests if item.get("references"))},
        ),
        "scene_registry": (
            _has_prompt_tokens(render_requests, ("lighting=", "mood=")),
            "Scene lighting and mood are compiled into shot prompts.",
            {"scene_locked_shots": sum(1 for item in render_requests if "lighting=" in str(item.get("prompt") or ""))},
        ),
        "qa_engine": (
            bool(qa_reports),
            f"QA reports={len(qa_reports)}, aggregate_passed={qa.get('passed')}.",
            {"qa_reports": len(qa_reports), "passed": qa.get("passed")},
        ),
        "retry_engine": (
            bool(retry_requests) or qa.get("passed") is True,
            f"Retry requests={len(retry_requests)}.",
            {"retry_requests": len(retry_requests)},
        ),
        "film_state_engine": (
            _has_continuity_parameters(render_requests),
            "Continuity parameters travel with every compiled render request.",
            {"continuity_locked_shots": sum(1 for item in render_requests if isinstance((item.get("parameters") or {}).get("continuity"), dict))},
        ),
    }

    stages: list[StageEvidence] = []
    for definition in ENGINE_STAGE_DEFINITIONS:
        done, evidence, metrics = evidence_by_stage[definition.id]
        stages.append(
            StageEvidence(
                id=definition.id,
                title=definition.title,
                owner=definition.owner,
                status=_stage_status(done),
                evidence=evidence,
                goal=definition.goal,
                artifacts=list(definition.artifacts),
                ui_surface=definition.ui_surface,
                metrics=metrics,
            )
        )
    return stages


def build_production_workflow_stage_index(summary: dict[str, Any]) -> list[StageEvidence]:
    """Return the Jellyfish-to-Film-Core production workflow stages."""

    workflow = list(summary.get("workflow") or JELLYFISH_FILM_WORKFLOW)
    render_requests = summary.get("render_requests") or []
    retry_requests = summary.get("retry_requests") or []
    qa = summary.get("qa") or {}
    post = summary.get("post_production") or {}
    metadata = summary.get("metadata") if isinstance(summary.get("metadata"), dict) else {}
    workflow_status = metadata.get("workflow_status") if isinstance(metadata.get("workflow_status"), dict) else {}
    stages: list[StageEvidence] = []
    for stage_id in workflow:
        owner = "Film Core"
        status = "done"
        evidence = "Structured stage emitted."
        metrics: dict[str, Any] = {}
        override = workflow_status.get(stage_id) if isinstance(workflow_status.get(stage_id), dict) else None
        if stage_id == "script_breakdown":
            owner = "Jellyfish"
            evidence = f"Project {summary.get('project', {}).get('id')} chapter {summary.get('chapter', {}).get('id')} indexed."
        elif stage_id == "runtime_adapter":
            owner = "Runtime"
            evidence = f"Render requests={len(render_requests)}."
            status = "done" if render_requests else "pending"
        elif stage_id == "qa_engine":
            owner = "QA"
            evidence = f"QA passed={qa.get('passed')}."
        elif stage_id == "retry_engine":
            owner = "QA"
            evidence = f"Retry requests={len(retry_requests)}."
            status = "done" if retry_requests or qa.get("passed") is True else "pending"
        elif stage_id == "final_export":
            owner = "Post"
            evidence = f"Post-production enabled={post.get('enabled')}."
            status = "done" if post.get("enabled") is not None else "pending"
        if override is not None:
            status = "done" if bool(override.get("done")) else "pending"
            evidence = str(override.get("evidence") or evidence)
            override_metrics = override.get("metrics")
            metrics = dict(override_metrics) if isinstance(override_metrics, dict) else {}
        title, owner = WORKFLOW_STAGE_TITLES.get(stage_id, (stage_id.replace("_", " ").title(), owner))
        stages.append(
            StageEvidence(
                id=stage_id,
                title=title,
                owner=owner,
                status=status,
                evidence=evidence,
                goal="Production workflow checkpoint.",
                artifacts=[],
                ui_surface="/film-engine",
                metrics=metrics,
            )
        )
    return stages


def build_industrial_review(status: JellyfishBaseStatus) -> list[IndustrialReviewItem]:
    base_status = "ready" if status.available else "blocked"
    return [
        IndustrialReviewItem(
            reference="Jellyfish",
            status=base_status,
            pain_point="Studio OS base",
            recommendation="Keep Jellyfish as project/chapter/shot/task platform and attach Film Core below it.",
        ),
        IndustrialReviewItem(
            reference="director_ai / BigBanana-AI-Director",
            status="tracked",
            pain_point="Camera randomness",
            recommendation="Compile camera DSL and pacing rules before any model prompt is emitted.",
        ),
        IndustrialReviewItem(
            reference="StoryDiffusion / Character Bible",
            status="tracked",
            pain_point="Character drift",
            recommendation="Resolve reference media, outfit, face identity terms, and negative terms per shot.",
        ),
        IndustrialReviewItem(
            reference="Prompt Compiler",
            status="tracked",
            pain_point="Prompt randomness",
            recommendation="Build prompts from structured state, never from one-off hardcoded prose.",
        ),
    ]


def build_studio_status(summary: dict[str, Any], base_status: JellyfishBaseStatus) -> dict[str, Any]:
    stages = build_stage_index(summary)
    workflow_stages = build_production_workflow_stage_index(summary)
    return {
        "summary": summary,
        "stages": [stage.__dict__ for stage in stages],
        "workflow_stages": [stage.__dict__ for stage in workflow_stages],
        "all_stages_done": all(stage.status == "done" for stage in stages),
        "industrial_review": [item.__dict__ for item in build_industrial_review(base_status)],
        "jellyfish": base_status.as_dict(),
    }
