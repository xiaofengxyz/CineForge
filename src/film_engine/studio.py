from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import JELLYFISH_FILM_WORKFLOW
from .jellyfish_base import JellyfishBaseStatus


@dataclass
class StageEvidence:
    id: str
    title: str
    owner: str
    status: str
    evidence: str


@dataclass
class IndustrialReviewItem:
    reference: str
    status: str
    pain_point: str
    recommendation: str


def build_stage_index(summary: dict[str, Any]) -> list[StageEvidence]:
    workflow = list(summary.get("workflow") or JELLYFISH_FILM_WORKFLOW)
    render_requests = summary.get("render_requests") or []
    retry_requests = summary.get("retry_requests") or []
    qa = summary.get("qa") or {}
    post = summary.get("post_production") or {}
    stages: list[StageEvidence] = []
    for stage_id in workflow:
        owner = "Film Core"
        status = "done"
        evidence = "Structured stage emitted."
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
        stages.append(StageEvidence(id=stage_id, title=stage_id.replace("_", " ").title(), owner=owner, status=status, evidence=evidence))
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
    return {
        "summary": summary,
        "stages": [stage.__dict__ for stage in build_stage_index(summary)],
        "industrial_review": [item.__dict__ for item in build_industrial_review(base_status)],
        "jellyfish": base_status.as_dict(),
    }

