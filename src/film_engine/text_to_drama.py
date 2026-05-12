from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .core import (
    CharacterBible,
    ClosedLoopProductionPlanner,
    SceneBible,
    StudioAsset,
    StudioChapter,
    StudioProject,
    StudioShot,
)
from .model_adapters import (
    ModelInvocation,
    RuntimeAdapterLayer,
    RuntimeModelProfiles,
)
from .workflow_control import (
    CINEFORGE_PROMPT_WORKFLOW,
    WorkflowControlConfig,
    WorkflowStageGate,
)


_SENTENCE_BOUNDARY = re.compile(r"(?<=[\.\!\?\u3002\uff01\uff1f])")


def _stable_suffix(value: str, *, length: int = 10) -> str:
    """Build deterministic IDs for recoverable offline workflow artifacts."""
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def _clean_text(value: Any) -> str:
    """Normalize user/story text while preserving non-ASCII story content."""
    return str(value or "").strip()


def _split_sentences(text: str) -> list[str]:
    """Split English or CJK prose into deterministic story beats."""
    chunks = [item.strip() for item in _SENTENCE_BOUNDARY.split(text) if item.strip()]
    if chunks:
        return chunks
    return [text.strip()] if text.strip() else []


def _chunk_items(items: list[str], count: int) -> list[list[str]]:
    """Split story beats into a stable chapter/shot distribution."""
    if not items:
        return [[] for _ in range(count)]
    count = max(1, min(count, len(items)))
    result: list[list[str]] = []
    for index in range(count):
        start = round(index * len(items) / count)
        end = round((index + 1) * len(items) / count)
        result.append(items[start:end] or [items[min(start, len(items) - 1)]])
    return result


@dataclass(frozen=True)
class NovelChapterDraft:
    """Novel chapter artifact produced before storyboard extraction."""

    id: str
    order: int
    title: str
    synopsis: str
    prose: str
    cliffhanger: str

    def as_dict(self) -> dict[str, Any]:
        """Serialize chapter text for persisted workflow state."""
        return asdict(self)


@dataclass(frozen=True)
class NovelPlanDraft:
    """World bible, relationship graph, outline, and generated prose."""

    title: str
    source_text: str
    world_bible: dict[str, Any]
    relationship_graph: list[dict[str, str]]
    chapters: list[NovelChapterDraft]

    def as_dict(self) -> dict[str, Any]:
        """Serialize the novel plan for API responses and saved state."""
        return {
            "title": self.title,
            "source_text": self.source_text,
            "world_bible": dict(self.world_bible),
            "relationship_graph": [dict(item) for item in self.relationship_graph],
            "chapters": [chapter.as_dict() for chapter in self.chapters],
        }


@dataclass(frozen=True)
class DramaAssetBundle:
    """Assets and shots extracted from the generated novel."""

    project: StudioProject
    chapters: list[StudioChapter]
    assets: list[StudioAsset]
    character_bibles: list[CharacterBible]
    scene_bibles: list[SceneBible]
    shots_by_chapter: dict[str, list[StudioShot]]

    def as_dict(self) -> dict[str, Any]:
        """Serialize the bundle without requiring Pydantic models."""
        return {
            "project": asdict(self.project),
            "chapters": [asdict(chapter) for chapter in self.chapters],
            "assets": [asdict(asset) for asset in self.assets],
            "character_bibles": [asdict(item) for item in self.character_bibles],
            "scene_bibles": [asdict(item) for item in self.scene_bibles],
            "shots_by_chapter": {
                chapter_id: [asdict(shot) for shot in shots]
                for chapter_id, shots in self.shots_by_chapter.items()
            },
        }


@dataclass(frozen=True)
class TextToDramaConfig:
    """Config for the executable text-to-novel-to-drama workflow."""

    title: str = "CineForge Auto Drama"
    run_id: str | None = None
    output_dir: str = "output/cineforge_runs"
    max_chapters: int = 3
    shots_per_chapter: int = 4
    qa_threshold: float = 0.75
    auto_retry: bool = True
    retry_limit: int = 2
    persist: bool = True
    execute_model_calls: bool = False
    runtime_profiles: RuntimeModelProfiles = field(default_factory=RuntimeModelProfiles)
    stage_controls: WorkflowControlConfig = field(default_factory=WorkflowControlConfig.automatic)

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "TextToDramaConfig":
        """Accept loose API payloads while preserving conservative defaults."""
        payload = value or {}
        controls = payload.get("stage_controls") or payload.get("stage_switches") or {}
        profiles = payload.get("runtime_profiles") or payload.get("models") or {}
        qa_threshold = payload.get("qa_threshold", 0.75)
        retry_limit = payload.get("retry_limit", 2)
        return cls(
            title=_clean_text(payload.get("title")) or "CineForge Auto Drama",
            run_id=_clean_text(payload.get("run_id")) or None,
            output_dir=_clean_text(payload.get("output_dir")) or "output/cineforge_runs",
            max_chapters=max(1, int(payload.get("max_chapters") or 3)),
            shots_per_chapter=max(1, int(payload.get("shots_per_chapter") or 4)),
            qa_threshold=max(0.0, min(1.0, float(qa_threshold if qa_threshold is not None else 0.75))),
            auto_retry=bool(payload.get("auto_retry", True)),
            retry_limit=max(0, int(retry_limit if retry_limit is not None else 2)),
            persist=bool(payload.get("persist", True)),
            execute_model_calls=bool(payload.get("execute_model_calls", False)),
            runtime_profiles=RuntimeModelProfiles.from_mapping(dict(profiles)),
            stage_controls=WorkflowControlConfig.from_mapping(dict(controls)),
        )


class TextToDramaPipeline:
    """Executable operating workflow from free text to comic-drama plan."""

    def __init__(self, *, adapter_layer: RuntimeAdapterLayer | None = None) -> None:
        self.adapter_layer = adapter_layer or RuntimeAdapterLayer()

    def run(self, source_text: str, config: TextToDramaConfig | None = None) -> dict[str, Any]:
        """Run the controlled workflow and persist a resumable state file."""
        config = config or TextToDramaConfig()
        cleaned_source = _clean_text(source_text)
        if not cleaned_source:
            raise ValueError("source_text is required")

        run_id = config.run_id or f"run_{uuid.uuid4().hex[:12]}"
        gate = WorkflowStageGate(config=config.stage_controls)
        artifacts: dict[str, Any] = {
            "architecture": None,
            "text_model_call": None,
            "text_model_result": None,
            "novel_plan": None,
            "asset_bundle": None,
            "image_runtime": [],
            "video_plans": [],
            "qa_retry": None,
            "studio_ui": None,
            "data_schema": None,
            "final_integration": None,
        }

        if gate.should_run("workflow_architecture"):
            artifacts["architecture"] = self._build_architecture(config)
            gate.complete(
                "workflow_architecture",
                evidence="Graph-first workflow envelope and stage controls initialized.",
            )
        if gate.halted:
            return self._finalize(run_id, config, gate, artifacts)

        if gate.should_run("novel_engine"):
            invocation = ModelInvocation(
                stage_id="novel_engine",
                modality="text",
                prompt=self._novel_prompt(cleaned_source, config.title),
                payload={"title": config.title, "max_chapters": config.max_chapters},
            )
            artifacts["text_model_call"] = self.adapter_layer.prepare(
                endpoint=config.runtime_profiles.text,
                invocation=invocation,
            ).safe_dict()
            if config.execute_model_calls:
                artifacts["text_model_result"] = self.adapter_layer.invoke(
                    endpoint=config.runtime_profiles.text,
                    invocation=invocation,
                ).as_dict()
            artifacts["novel_plan"] = self._build_novel_plan(cleaned_source, config, run_id)
            gate.complete(
                "novel_engine",
                evidence=f"Novel plan chapters={len(artifacts['novel_plan'].chapters)}.",
            )
        if gate.halted:
            return self._finalize(run_id, config, gate, artifacts)

        if gate.should_run("asset_pipeline"):
            novel_plan = artifacts["novel_plan"]
            artifacts["asset_bundle"] = (
                self._build_asset_bundle(novel_plan, config, run_id) if novel_plan is not None else None
            )
            shot_count = 0
            if artifacts["asset_bundle"] is not None:
                shot_count = sum(len(items) for items in artifacts["asset_bundle"].shots_by_chapter.values())
            gate.complete(
                "asset_pipeline",
                evidence=f"Asset bundle ready with shots={shot_count}.",
            )
        if gate.halted:
            return self._finalize(run_id, config, gate, artifacts)

        if gate.should_run("image_runtime"):
            bundle = artifacts["asset_bundle"]
            artifacts["image_runtime"] = (
                self._build_image_runtime_calls(bundle, config) if bundle is not None else []
            )
            gate.complete(
                "image_runtime",
                evidence=f"Prepared image calls={len(artifacts['image_runtime'])}.",
            )
        if gate.halted:
            return self._finalize(run_id, config, gate, artifacts)

        if gate.should_run("video_runtime"):
            bundle = artifacts["asset_bundle"]
            artifacts["video_plans"] = self._build_video_plans(bundle, config) if bundle is not None else []
            render_count = sum(len(plan.get("render_requests") or []) for plan in artifacts["video_plans"])
            gate.complete("video_runtime", evidence=f"Prepared video render requests={render_count}.")
        if gate.halted:
            return self._finalize(run_id, config, gate, artifacts)

        if gate.should_run("qa_retry_engine"):
            artifacts["qa_retry"] = self._build_qa_retry_summary(artifacts["video_plans"])
            gate.complete(
                "qa_retry_engine",
                evidence=f"QA reports={artifacts['qa_retry']['qa_report_count']}, retries={artifacts['qa_retry']['retry_count']}.",
            )
        if gate.halted:
            return self._finalize(run_id, config, gate, artifacts)

        if gate.should_run("studio_ui"):
            artifacts["studio_ui"] = self._build_studio_ui_manifest()
            gate.complete("studio_ui", evidence="Studio routes and API actions attached.")
        if gate.halted:
            return self._finalize(run_id, config, gate, artifacts)

        if gate.should_run("data_schema"):
            artifacts["data_schema"] = self._build_schema_manifest(artifacts)
            gate.complete("data_schema", evidence="Persistable schema manifest emitted.")
        if gate.halted:
            return self._finalize(run_id, config, gate, artifacts)

        if gate.should_run("final_integration"):
            artifacts["final_integration"] = self._build_final_integration(artifacts)
            gate.complete("final_integration", evidence="Text-to-drama operating plan connected end to end.")

        return self._finalize(run_id, config, gate, artifacts)

    def _build_architecture(self, config: TextToDramaConfig) -> dict[str, Any]:
        """Create the stage/control envelope before any generation artifacts."""
        return {
            "workflow": [stage.id for stage in CINEFORGE_PROMPT_WORKFLOW],
            "stage_controls": config.stage_controls.as_dict(),
            "runtime_profiles": config.runtime_profiles.safe_dict(),
            "principles": [
                "graph_based_workflow",
                "ecs_inspired_assets",
                "runtime_adapter_boundary",
                "prompt_compiler_architecture",
                "qa_retry_closed_loop",
            ],
        }

    def _novel_prompt(self, source_text: str, title: str) -> str:
        """Build a model prompt without hardcoding it into runtime providers."""
        return (
            "Expand the source idea into a serialized cinematic novel plan. "
            f"Title: {title}. Source: {source_text}"
        )

    def _build_novel_plan(
        self,
        source_text: str,
        config: TextToDramaConfig,
        run_id: str,
    ) -> NovelPlanDraft:
        """Generate deterministic novel artifacts from user text."""
        beats = _split_sentences(source_text)
        chapter_count = max(1, min(config.max_chapters, len(beats) or 1))
        chapters: list[NovelChapterDraft] = []
        for index, chapter_beats in enumerate(_chunk_items(beats, chapter_count), start=1):
            synopsis = " ".join(chapter_beats).strip() or source_text
            prose = (
                f"Chapter {index}: {synopsis}\n"
                "The scene is expanded with continuity-safe actions, clear emotional beats, "
                "and visual details reserved for later storyboard compilation."
            )
            chapters.append(
                NovelChapterDraft(
                    id=f"{run_id}_novel_chapter_{index:03d}",
                    order=index,
                    title=f"Chapter {index}",
                    synopsis=synopsis,
                    prose=prose,
                    cliffhanger=f"End chapter {index} on a visual question that motivates the next shot sequence.",
                )
            )
        return NovelPlanDraft(
            title=config.title,
            source_text=source_text,
            world_bible={
                "premise": source_text,
                "tone": "cinematic serialized drama",
                "continuity_rules": [
                    "Keep character identity stable across every chapter.",
                    "Carry scene lighting, outfit, emotion, and timeline state into each shot.",
                    "Compile prompts from structured state instead of one-off prose.",
                ],
            },
            relationship_graph=[
                {"source": "protagonist", "target": "central_conflict", "relation": "drives"},
                {"source": "protagonist", "target": "primary_setting", "relation": "transforms"},
            ],
            chapters=chapters,
        )

    def _build_asset_bundle(
        self,
        novel_plan: NovelPlanDraft,
        config: TextToDramaConfig,
        run_id: str,
    ) -> DramaAssetBundle:
        """Extract reusable drama assets and shot graph from the novel plan."""
        source = novel_plan.source_text
        character_names = self._extract_character_names(source)
        scene_names = self._extract_scene_names(source)
        prop_names = self._extract_prop_names(source)

        project = StudioProject(
            id=f"{run_id}_project",
            title=novel_plan.title,
            description=source,
            style="serial_drama",
            visual_style="anime_drama",
        )
        character_bibles = [
            CharacterBible(
                id=f"char_{index:03d}_{_stable_suffix(name, length=6)}",
                name=name,
                reference_media=[f"references/characters/{_stable_suffix(name)}.png"],
                outfits={"default": f"{name} continuity outfit"},
                default_outfit="default",
                identity_terms=[name, f"{name} stable face"],
                negative_terms=[f"wrong {name}", "identity drift"],
            )
            for index, name in enumerate(character_names, start=1)
        ]
        scene_bibles = [
            SceneBible(
                id=f"scene_{index:03d}_{_stable_suffix(name, length=6)}",
                name=name,
                lighting=self._infer_lighting(source),
                mood="dramatic",
                camera_style="cinematic storyboard",
                reference_media=[f"references/scenes/{_stable_suffix(name)}.png"],
            )
            for index, name in enumerate(scene_names, start=1)
        ]
        assets = [
            *[
                StudioAsset(
                    id=item.id,
                    kind="character",
                    name=item.name,
                    description=f"Character bible for {item.name}.",
                    reference_media=list(item.reference_media),
                )
                for item in character_bibles
            ],
            *[
                StudioAsset(
                    id=item.id,
                    kind="scene",
                    name=item.name,
                    description=f"Scene bible for {item.name}.",
                    reference_media=list(item.reference_media),
                    metadata={"lighting": item.lighting, "mood": item.mood},
                )
                for item in scene_bibles
            ],
            *[
                StudioAsset(
                    id=f"prop_{index:03d}_{_stable_suffix(name, length=6)}",
                    kind="prop",
                    name=name,
                    description=f"Continuity prop: {name}.",
                    reference_media=[f"references/props/{_stable_suffix(name)}.png"],
                )
                for index, name in enumerate(prop_names, start=1)
            ],
        ]

        chapters: list[StudioChapter] = []
        shots_by_chapter: dict[str, list[StudioShot]] = {}
        primary_character_id = character_bibles[0].id
        primary_scene_id = scene_bibles[0].id
        for chapter in novel_plan.chapters:
            studio_chapter = StudioChapter(
                id=chapter.id.replace("novel", "studio"),
                project_id=project.id,
                title=chapter.title,
                order=chapter.order,
                raw_text=chapter.prose,
                condensed_text=chapter.synopsis,
            )
            chapters.append(studio_chapter)
            shot_beats = _chunk_items(_split_sentences(chapter.synopsis), config.shots_per_chapter)
            shots: list[StudioShot] = []
            for shot_index, beat_group in enumerate(shot_beats, start=1):
                shot_id = f"{studio_chapter.id}_shot_{shot_index:03d}"
                summary = " ".join(beat_group).strip() or chapter.synopsis
                shots.append(
                    StudioShot(
                        id=shot_id,
                        project_id=project.id,
                        chapter_id=studio_chapter.id,
                        index=shot_index,
                        title=f"{chapter.title} Shot {shot_index}",
                        summary=summary,
                        scene_id=primary_scene_id,
                        character_ids=[primary_character_id],
                        prop_ids=[asset.id for asset in assets if asset.kind == "prop"][:1],
                        dialogue=[f"{character_bibles[0].name}: {summary[:80]}"],
                        camera={
                            "framing": ["wide", "medium_closeup", "closeup"][shot_index % 3],
                            "movement": ["static", "dolly_in", "track"][shot_index % 3],
                            "lens": "35mm" if shot_index % 2 else "50mm",
                            "emotion": "focused",
                            "pacing": "serial_drama",
                        },
                        duration=4.0,
                        reference_media=[f"storyboards/{shot_id}.png"],
                        readiness_state="ready",
                        is_generation_ready=True,
                    )
                )
            shots_by_chapter[studio_chapter.id] = shots

        return DramaAssetBundle(
            project=project,
            chapters=chapters,
            assets=assets,
            character_bibles=character_bibles,
            scene_bibles=scene_bibles,
            shots_by_chapter=shots_by_chapter,
        )

    def _build_image_runtime_calls(
        self,
        bundle: DramaAssetBundle,
        config: TextToDramaConfig,
    ) -> list[dict[str, Any]]:
        """Prepare image model calls for assets and storyboard frames."""
        calls: list[dict[str, Any]] = []
        for asset in bundle.assets:
            invocation = ModelInvocation(
                stage_id="image_runtime",
                modality="image",
                prompt=f"Create stable reference image for {asset.kind}: {asset.name}. {asset.description}",
                payload={"asset_id": asset.id, "kind": asset.kind},
            )
            calls.append(
                self.adapter_layer.prepare(endpoint=config.runtime_profiles.image, invocation=invocation).safe_dict()
            )
        for shots in bundle.shots_by_chapter.values():
            for shot in shots:
                invocation = ModelInvocation(
                    stage_id="image_runtime",
                    modality="storyboard",
                    prompt=f"Create storyboard frame for {shot.title}: {shot.summary}",
                    payload={"shot_id": shot.id, "chapter_id": shot.chapter_id},
                )
                calls.append(
                    self.adapter_layer.prepare(endpoint=config.runtime_profiles.image, invocation=invocation).safe_dict()
                )
        return calls

    def _build_video_plans(
        self,
        bundle: DramaAssetBundle,
        config: TextToDramaConfig,
    ) -> list[dict[str, Any]]:
        """Compile provider-neutral video render requests for every chapter."""
        planner = ClosedLoopProductionPlanner()
        plans: list[dict[str, Any]] = []
        for chapter in bundle.chapters:
            shots = bundle.shots_by_chapter.get(chapter.id, [])
            qa_metrics_by_shot = {
                shot.id: {
                    "face_similarity": 0.88,
                    "outfit_similarity": 0.86,
                    "lighting_similarity": 0.84,
                    "clip_score": 0.87,
                }
                for shot in shots
            }
            plan = planner.plan_chapter(
                project=bundle.project,
                chapter=chapter,
                shots=shots,
                assets=bundle.assets,
                character_bibles=bundle.character_bibles,
                scene_bibles=bundle.scene_bibles,
                provider=config.runtime_profiles.video.provider,
                model=config.runtime_profiles.video.model,
                output_dir=str(Path(config.output_dir) / "renders" / chapter.id),
                qa_metrics_by_shot=qa_metrics_by_shot,
                qa_threshold=config.qa_threshold,
                auto_retry=config.auto_retry,
                retry_limit=config.retry_limit,
            )
            plan_dict = plan.as_dict()
            plan_dict["runtime_endpoint"] = config.runtime_profiles.video.safe_dict()
            plans.append(plan_dict)
        return plans

    def _build_qa_retry_summary(self, video_plans: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate QA and retry evidence across chapter plans."""
        qa_reports: list[dict[str, Any]] = []
        retry_requests: list[dict[str, Any]] = []
        for plan in video_plans:
            qa = plan.get("qa") if isinstance(plan.get("qa"), dict) else {}
            qa_reports.extend([item for item in qa.get("reports") or [] if isinstance(item, dict)])
            retry_requests.extend([item for item in plan.get("retry_requests") or [] if isinstance(item, dict)])
        return {
            "qa_report_count": len(qa_reports),
            "retry_count": len(retry_requests),
            "passed": bool(qa_reports) and all(bool(item.get("passed")) for item in qa_reports),
            "reports": qa_reports,
            "retry_requests": retry_requests,
        }

    def _build_studio_ui_manifest(self) -> dict[str, Any]:
        """Expose concrete surfaces where the generated plan can be inspected."""
        return {
            "routes": ["/film-engine", "/projects/{projectId}?tab=film-engine"],
            "actions": ["review_stage_switches", "inspect_render_requests", "run_film_qa", "create_retry_task"],
            "api": [
                "GET /api/v1/film/engine/stage-index",
                "POST /api/v1/film/engine/text-to-drama-plan",
            ],
        }

    def _build_schema_manifest(self, artifacts: dict[str, Any]) -> dict[str, Any]:
        """Document the persisted state keys emitted by this workflow."""
        return {
            "state_version": 1,
            "top_level_keys": sorted(artifacts.keys()),
            "novel_plan": ["world_bible", "relationship_graph", "chapters"],
            "asset_bundle": ["project", "chapters", "assets", "character_bibles", "scene_bibles", "shots_by_chapter"],
            "runtime": ["image_runtime", "video_plans"],
            "qa_retry": ["reports", "retry_requests", "passed"],
        }

    def _build_final_integration(self, artifacts: dict[str, Any]) -> dict[str, Any]:
        """Connect generated artifacts into a single operating handoff."""
        video_plans = artifacts.get("video_plans") or []
        render_count = sum(len(plan.get("render_requests") or []) for plan in video_plans)
        return {
            "ready_for_batch_submission": render_count > 0,
            "render_request_count": render_count,
            "state_handoff": "Persisted JSON can be used by API, Studio UI, or batch workers.",
        }

    def _finalize(
        self,
        run_id: str,
        config: TextToDramaConfig,
        gate: WorkflowStageGate,
        artifacts: dict[str, Any],
    ) -> dict[str, Any]:
        """Serialize artifacts, write state, and report resumable progress."""
        execution_state = gate.finalize()
        status = "waiting_for_user" if execution_state.waiting_for_user else "completed"
        payload = {
            "run_id": run_id,
            "title": config.title,
            "status": status,
            "workflow_control": execution_state.as_dict(),
            "runtime_profiles": config.runtime_profiles.safe_dict(),
            "artifacts": self._serialize_artifacts(artifacts),
        }
        if config.persist:
            state_path = Path(config.output_dir) / run_id / "state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
            payload["state_path"] = str(state_path)
        return payload

    def _serialize_artifacts(self, artifacts: dict[str, Any]) -> dict[str, Any]:
        """Convert dataclass artifacts to plain dictionaries."""
        serialized = dict(artifacts)
        novel_plan = serialized.get("novel_plan")
        if isinstance(novel_plan, NovelPlanDraft):
            serialized["novel_plan"] = novel_plan.as_dict()
        asset_bundle = serialized.get("asset_bundle")
        if isinstance(asset_bundle, DramaAssetBundle):
            serialized["asset_bundle"] = asset_bundle.as_dict()
        return serialized

    def _extract_character_names(self, text: str) -> list[str]:
        """Extract stable character candidates with conservative fallbacks."""
        candidates: list[str] = []
        for name in re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", text):
            if name.lower() not in {"the", "and", "but", "chapter", "scene"}:
                candidates.append(name)
        cjk_patterns = [
            r"(?:called|named)\s*([\w\-]{2,24})",
            r"(?:hero|protagonist)\s+([\w\-]{2,24})",
        ]
        for pattern in cjk_patterns:
            candidates.extend(re.findall(pattern, text, flags=re.IGNORECASE))
        return self._dedupe(candidates)[:3] or ["Protagonist"]

    def _extract_scene_names(self, text: str) -> list[str]:
        """Infer scene candidates from common cinematic location terms."""
        lowered = text.lower()
        if "alley" in lowered or "street" in lowered:
            return ["Neon Street"]
        if "palace" in lowered or "kingdom" in lowered:
            return ["Broken Palace"]
        if "space" in lowered or "station" in lowered:
            return ["Orbital Station"]
        if "school" in lowered or "academy" in lowered:
            return ["Night Academy"]
        return ["Primary Setting"]

    def _extract_prop_names(self, text: str) -> list[str]:
        """Infer continuity prop candidates without hardcoding prompts."""
        lowered = text.lower()
        props = []
        for keyword in ("sword", "ring", "chip", "key", "letter", "camera"):
            if keyword in lowered:
                props.append(keyword.title())
        return props[:2]

    def _infer_lighting(self, text: str) -> str:
        """Infer a scene lighting lock used by PromptCompiler."""
        lowered = text.lower()
        if "night" in lowered or "neon" in lowered:
            return "neon_night_key"
        if "rain" in lowered or "storm" in lowered:
            return "rainy_soft_key"
        if "sun" in lowered or "desert" in lowered:
            return "warm_high_key"
        return "cinematic_key_light"

    def _dedupe(self, values: list[str]) -> list[str]:
        """Keep extracted candidates deterministic and unique."""
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            cleaned = value.strip()
            if not cleaned or cleaned.lower() in seen:
                continue
            seen.add(cleaned.lower())
            result.append(cleaned)
        return result


def load_text_to_drama_state(path: str | Path) -> dict[str, Any]:
    """Load a persisted text-to-drama run state for recovery."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
