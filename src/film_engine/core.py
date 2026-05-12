from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


JELLYFISH_FILM_WORKFLOW = [
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


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


@dataclass
class Component:
    name: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class Entity:
    id: str
    kind: str
    components: dict[str, Component] = field(default_factory=dict)

    def add_component(self, name: str, data: dict[str, Any]) -> Component:
        component = Component(name=name, data=dict(data))
        self.components[name] = component
        return component

    def get_component(self, name: str) -> Component:
        return self.components[name]


class EntityRegistry:
    def __init__(self) -> None:
        self._items: dict[str, Entity] = {}

    def register(self, entity: Entity) -> Entity:
        self._items[entity.id] = entity
        return entity

    def get(self, entity_id: str) -> Entity | None:
        return self._items.get(entity_id)

    def all(self) -> list[Entity]:
        return list(self._items.values())


@dataclass
class WorkflowNode:
    id: str
    system: str
    payload: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)


class WorkflowGraph:
    def __init__(self) -> None:
        self.nodes: list[WorkflowNode] = []

    def add_node(
        self,
        system: str,
        *,
        node_id: str | None = None,
        payload: dict[str, Any] | None = None,
        depends_on: list[str] | None = None,
    ) -> WorkflowNode:
        node = WorkflowNode(
            id=node_id or system,
            system=system,
            payload=payload or {},
            depends_on=list(depends_on or []),
        )
        self.nodes.append(node)
        return node

    def topological_order(self) -> list[WorkflowNode]:
        # The graph is built as a stage chain today. Keeping this explicit
        # object makes later LangGraph/ComfyUI-style execution swappable.
        return list(self.nodes)


@dataclass
class StudioProject:
    id: str
    title: str
    description: str = ""
    style: str | None = None
    visual_style: str | None = None
    chapter_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StudioChapter:
    id: str
    project_id: str
    title: str
    order: int = 1
    shot_ids: list[str] = field(default_factory=list)
    raw_text: str = ""
    condensed_text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StudioAsset:
    id: str
    kind: str
    name: str
    description: str = ""
    reference_media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StudioShot:
    id: str
    project_id: str
    chapter_id: str
    index: int
    title: str = ""
    summary: str = ""
    scene_id: str | None = None
    character_ids: list[str] = field(default_factory=list)
    prop_ids: list[str] = field(default_factory=list)
    costume_ids: list[str] = field(default_factory=list)
    dialogue: list[str] = field(default_factory=list)
    camera: dict[str, Any] = field(default_factory=dict)
    duration: float | None = None
    reference_media: list[str] = field(default_factory=list)
    readiness_state: str = ""
    is_generation_ready: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StudioTask:
    id: str
    project_id: str
    task_type: str
    status: str
    shot_id: str | None = None
    result_media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CharacterBible:
    id: str
    name: str
    reference_media: list[str] = field(default_factory=list)
    outfits: dict[str, str] = field(default_factory=dict)
    default_outfit: str | None = None
    voice_id: str | None = None
    lora: str | None = None
    embeddings: list[str] = field(default_factory=list)
    identity_terms: list[str] = field(default_factory=list)
    negative_terms: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def resolve_outfit(self) -> str | None:
        if self.default_outfit and self.default_outfit in self.outfits:
            return self.outfits[self.default_outfit]
        if self.outfits:
            return next(iter(self.outfits.values()))
        return None


@dataclass
class SceneBible:
    id: str
    name: str
    location: str = ""
    lighting: str = ""
    weather: str = ""
    tone: str = ""
    mood: str = ""
    camera_style: str = ""
    reference_media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ShotContinuityState:
    shot_id: str
    character_ids: list[str] = field(default_factory=list)
    scene_id: str | None = None
    prop_ids: list[str] = field(default_factory=list)
    costume_ids: list[str] = field(default_factory=list)
    outfit_map: dict[str, str] = field(default_factory=dict)
    emotion_map: dict[str, str] = field(default_factory=dict)
    lighting: str = ""
    timeline_position: str = ""
    reference_media: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleIssue:
    code: str
    message: str
    severity: str = "medium"
    field: str | None = None


@dataclass
class RuleResult:
    passed: bool
    issues: list[RuleIssue] = field(default_factory=list)


class DirectorRuleEngine:
    required_fields = ("framing", "movement", "lens", "emotion")

    def validate_dsl(self, dsl: dict[str, Any]) -> RuleResult:
        issues: list[RuleIssue] = []
        for field_name in self.required_fields:
            if not str(dsl.get(field_name, "")).strip():
                issues.append(
                    RuleIssue(
                        code=f"missing_{field_name}",
                        message=f"Director DSL missing {field_name}.",
                        severity="high" if field_name in {"lens", "emotion"} else "medium",
                        field=field_name,
                    )
                )
        duration = dsl.get("duration")
        if duration is not None and float(duration or 0) <= 0:
            issues.append(
                RuleIssue(
                    code="invalid_duration",
                    message="Shot duration must be greater than zero.",
                    severity="high",
                    field="duration",
                )
            )
        return RuleResult(passed=not issues, issues=issues)


@dataclass
class DirectorPreparedShot:
    shot: StudioShot
    continuity: ShotContinuityState
    director_dsl: dict[str, Any]
    passed: bool
    issues: list[RuleIssue] = field(default_factory=list)


class DirectorConsistencyEngine:
    def prepare_shot(
        self,
        *,
        shot: StudioShot,
        continuity: ShotContinuityState,
        character_bibles: list[CharacterBible],
        scene_bibles: list[SceneBible],
    ) -> DirectorPreparedShot:
        characters = {item.id: item for item in character_bibles}
        scenes = {item.id: item for item in scene_bibles}
        issues: list[RuleIssue] = []

        for character_id in shot.character_ids or continuity.character_ids:
            if character_id not in characters:
                issues.append(
                    RuleIssue(
                        code="missing_character_bible",
                        message=f"Missing character bible for {character_id}.",
                        severity="high",
                        field="character_ids",
                    )
                )

        if shot.scene_id or continuity.scene_id:
            scene_id = shot.scene_id or continuity.scene_id
            if scene_id not in scenes:
                issues.append(
                    RuleIssue(
                        code="missing_scene_bible",
                        message=f"Missing scene bible for {scene_id}.",
                        severity="high",
                        field="scene_id",
                    )
                )

        prepared = ShotContinuityState(
            shot_id=continuity.shot_id,
            character_ids=list(continuity.character_ids or shot.character_ids),
            scene_id=continuity.scene_id or shot.scene_id,
            prop_ids=list(continuity.prop_ids or shot.prop_ids),
            costume_ids=list(continuity.costume_ids or shot.costume_ids),
            outfit_map=dict(continuity.outfit_map),
            emotion_map=dict(continuity.emotion_map),
            lighting=continuity.lighting,
            timeline_position=continuity.timeline_position,
            reference_media=list(continuity.reference_media),
            metadata=dict(continuity.metadata),
        )

        voice_map: dict[str, str] = {}
        character_context: dict[str, dict[str, Any]] = {}
        emotion = str(shot.camera.get("emotion", "") or "")
        for character_id in shot.character_ids:
            bible = characters.get(character_id)
            if not bible:
                continue
            outfit = bible.resolve_outfit()
            if outfit and character_id not in prepared.outfit_map:
                prepared.outfit_map[character_id] = outfit
            if emotion and character_id not in prepared.emotion_map:
                prepared.emotion_map[character_id] = emotion
            if bible.voice_id:
                voice_map[character_id] = bible.voice_id
            character_context[character_id] = {
                "name": bible.name,
                "lora": bible.lora,
                "embeddings": list(bible.embeddings),
                "identity_terms": list(bible.identity_terms),
                "negative_terms": list(bible.negative_terms),
                "outfit": outfit,
                "reference_media": list(bible.reference_media),
            }
            prepared.reference_media.extend(bible.reference_media)

        scene_mood = ""
        scene = scenes.get(prepared.scene_id or "")
        if scene:
            prepared.lighting = prepared.lighting or scene.lighting
            scene_mood = scene.mood
            prepared.reference_media.extend(scene.reference_media)

        prepared.reference_media = _dedupe(prepared.reference_media)
        director_dsl = {
            **shot.camera,
            "shot_id": shot.id,
            "duration": shot.duration,
            "summary": shot.summary,
            "dialogue": list(shot.dialogue),
            "voice_map": voice_map,
            "character_context": character_context,
            "scene_mood": scene_mood,
            "scene_id": prepared.scene_id,
        }
        rule_result = DirectorRuleEngine().validate_dsl(director_dsl)
        issues.extend(rule_result.issues)
        return DirectorPreparedShot(
            shot=shot,
            continuity=prepared,
            director_dsl=director_dsl,
            passed=not issues,
            issues=issues,
        )


@dataclass
class CompiledPrompt:
    provider: str
    text: str
    negative_text: str = ""
    references: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)


class PromptCompiler:
    def compile_shot(
        self,
        *,
        provider: str,
        director_dsl: dict[str, Any],
        continuity: ShotContinuityState,
    ) -> CompiledPrompt:
        camera_parts = [
            f"shot={director_dsl.get('shot_id', continuity.shot_id)}",
            f"framing={director_dsl.get('framing', '')}",
            f"movement={director_dsl.get('movement', '')}",
            f"lens={director_dsl.get('lens', '')}",
            f"emotion={director_dsl.get('emotion', '')}",
        ]
        if director_dsl.get("pacing"):
            camera_parts.append(f"pacing={director_dsl['pacing']}")
        if continuity.lighting:
            camera_parts.append(f"lighting={continuity.lighting}")
        if director_dsl.get("scene_mood"):
            camera_parts.append(f"mood={director_dsl['scene_mood']}")
        if continuity.outfit_map:
            outfits = ",".join(f"{key}:{value}" for key, value in sorted(continuity.outfit_map.items()))
            camera_parts.append(f"outfits={outfits}")
        if continuity.emotion_map:
            emotions = ",".join(f"{key}:{value}" for key, value in sorted(continuity.emotion_map.items()))
            camera_parts.append(f"character_emotions={emotions}")
        if director_dsl.get("summary"):
            camera_parts.append(f"action={director_dsl['summary']}")

        character_context = director_dsl.get("character_context") or {}
        negative_terms: list[str] = []
        identity_terms: list[str] = []
        for context in character_context.values():
            negative_terms.extend(context.get("negative_terms") or [])
            identity_terms.extend(context.get("identity_terms") or [])
        if identity_terms:
            camera_parts.append(f"identity={','.join(identity_terms)}")

        provider_prefix = {
            "kling": "cinematic live-action, stable identity",
            "seedance": "film-grade motion, continuity locked",
            "veo": "natural cinematic realism, long-take consistency",
        }.get(provider, "cinematic continuity locked")
        text = "; ".join([provider_prefix, *[part for part in camera_parts if not part.endswith("=")]])
        return CompiledPrompt(
            provider=provider,
            text=text,
            negative_text=", ".join(_dedupe(negative_terms)),
            references=list(continuity.reference_media),
            parameters={
                "provider": provider,
                "voice_map": dict(director_dsl.get("voice_map") or {}),
                "camera": {
                    "framing": director_dsl.get("framing"),
                    "movement": director_dsl.get("movement"),
                    "lens": director_dsl.get("lens"),
                    "duration": director_dsl.get("duration"),
                },
                "continuity": {
                    "outfit_map": dict(continuity.outfit_map),
                    "emotion_map": dict(continuity.emotion_map),
                    "lighting": continuity.lighting,
                    "timeline_position": continuity.timeline_position,
                },
            },
        )


@dataclass
class RenderRequest:
    shot_id: str
    provider: str
    model: str
    prompt: str
    output_path: str
    references: list[str] = field(default_factory=list)
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderResult:
    shot_id: str
    output_path: str
    runtime: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QAIssue:
    code: str
    message: str
    severity: str
    metric: str
    score: float | None = None
    threshold: float | None = None


@dataclass
class QAReport:
    shot_id: str
    passed: bool
    score: float
    issues: list[QAIssue] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


class QAEngine:
    default_thresholds = {
        "face_similarity": 0.75,
        "outfit_similarity": 0.70,
        "lighting_similarity": 0.60,
        "clip_score": 0.55,
    }

    issue_codes = {
        "face_similarity": "low_face_similarity",
        "outfit_similarity": "outfit_drift",
        "lighting_similarity": "lighting_mismatch",
        "clip_score": "weak_prompt_alignment",
    }

    def __init__(
        self,
        *,
        thresholds: dict[str, float] | None = None,
        default_threshold: float | None = None,
    ) -> None:
        if thresholds is not None:
            self.thresholds = dict(thresholds)
        elif default_threshold is not None:
            value = max(0.0, min(1.0, float(default_threshold)))
            self.thresholds = {metric: value for metric in self.default_thresholds}
        else:
            self.thresholds = dict(self.default_thresholds)

    def evaluate(self, *, shot_id: str, metrics: dict[str, float] | None = None) -> QAReport:
        metrics = dict(metrics or {})
        issues: list[QAIssue] = []
        scores: list[float] = []
        for metric, threshold in self.thresholds.items():
            if metric not in metrics:
                continue
            score = float(metrics[metric])
            scores.append(score)
            if score < threshold:
                issues.append(
                    QAIssue(
                        code=self.issue_codes[metric],
                        message=f"{metric}={score:.2f} below threshold {threshold:.2f}.",
                        severity="high" if metric in {"face_similarity", "outfit_similarity"} else "medium",
                        metric=metric,
                        score=score,
                        threshold=threshold,
                    )
                )
        aggregate = min(scores) if scores else 1.0
        return QAReport(shot_id=shot_id, passed=not issues, score=aggregate, issues=issues, metrics=metrics)


@dataclass
class RetryRequest:
    shot_id: str
    prompt: str
    parameters: dict[str, Any] = field(default_factory=dict)
    reason_codes: list[str] = field(default_factory=list)


class RetryEngine:
    def build_retry_request(
        self,
        *,
        report: QAReport,
        compiled_prompt: CompiledPrompt,
        attempt: int = 2,
    ) -> RetryRequest | None:
        if report.passed:
            return None
        repair_lines: list[str] = []
        parameters: dict[str, Any] = {"retry_attempt": attempt}
        for issue in report.issues:
            if issue.metric == "face_similarity":
                parameters["reference_strength"] = "high"
                repair_lines.append("Increase reference strength for face_similarity.")
            elif issue.metric == "outfit_similarity":
                parameters["lock_outfit"] = True
                repair_lines.append("Lock wardrobe and costume descriptors.")
            elif issue.metric == "lighting_similarity":
                parameters["lock_lighting"] = True
                repair_lines.append("Match scene lighting and color temperature.")
            elif issue.metric == "clip_score":
                parameters["prompt_alignment"] = "strict"
                repair_lines.append("Tighten action and composition alignment.")
        prompt = f"{compiled_prompt.text}; retry repair: {' '.join(repair_lines)}"
        return RetryRequest(
            shot_id=report.shot_id,
            prompt=prompt,
            parameters=parameters,
            reason_codes=[issue.code for issue in report.issues],
        )


@dataclass
class ShotPlan:
    shot: StudioShot
    continuity: ShotContinuityState
    compiled_prompt: CompiledPrompt
    render_request: RenderRequest
    qa_report: QAReport
    retry_request: RetryRequest | None = None


@dataclass
class ClosedLoopProductionPlan:
    project: StudioProject
    chapter: StudioChapter
    workflow: WorkflowGraph
    shot_plans: list[ShotPlan]
    render_requests: list[RenderRequest]
    qa_passed: bool
    retry_requests: list[RetryRequest]
    metadata: dict[str, Any] = field(default_factory=dict)
    post_production_plan: Any | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "project": {"id": self.project.id, "title": self.project.title},
            "chapter": {"id": self.chapter.id, "title": self.chapter.title},
            "workflow": [node.system for node in self.workflow.topological_order()],
            "metadata": dict(self.metadata),
            "render_requests": [
                {
                    "shot_id": item.shot_id,
                    "provider": item.provider,
                    "model": item.model,
                    "prompt": item.prompt,
                    "references": list(item.references),
                    "output_path": item.output_path,
                    "parameters": dict(item.parameters),
                }
                for item in self.render_requests
            ],
            "qa": {
                "passed": self.qa_passed,
                "reports": [
                    {
                        "shot_id": item.qa_report.shot_id,
                        "passed": item.qa_report.passed,
                        "score": item.qa_report.score,
                        "metrics": dict(item.qa_report.metrics),
                        "issues": [issue.__dict__ for issue in item.qa_report.issues],
                    }
                    for item in self.shot_plans
                ],
            },
            "retry_requests": [
                {
                    "shot_id": item.shot_id,
                    "prompt": item.prompt,
                    "parameters": dict(item.parameters),
                    "reason_codes": list(item.reason_codes),
                }
                for item in self.retry_requests
            ],
            "post_production": {
                "enabled": self.post_production_plan is not None,
                "output_path": getattr(self.post_production_plan, "output_path", None),
            },
        }


class ClosedLoopProductionPlanner:
    def __init__(self) -> None:
        from .platform import StudioPlatformBridge

        self.bridge = StudioPlatformBridge()
        self.director = DirectorConsistencyEngine()
        self.compiler = PromptCompiler()
        self.qa = QAEngine()
        self.retry = RetryEngine()

    def plan_chapter(
        self,
        *,
        project: StudioProject,
        chapter: StudioChapter,
        shots: list[StudioShot],
        assets: list[StudioAsset],
        character_bibles: list[CharacterBible],
        scene_bibles: list[SceneBible],
        provider: str,
        model: str,
        output_dir: str,
        qa_metrics_by_shot: dict[str, dict[str, float]] | None = None,
        render_results: list[RenderResult] | None = None,
        export_output_path: str | None = None,
        qa_threshold: float | None = None,
        auto_retry: bool = True,
        retry_limit: int | None = None,
    ) -> ClosedLoopProductionPlan:
        workflow = self.bridge.build_chapter_workflow(project, chapter, shots)
        shot_plans: list[ShotPlan] = []
        render_requests: list[RenderRequest] = []
        retry_requests: list[RetryRequest] = []
        qa_engine = QAEngine(default_threshold=qa_threshold) if qa_threshold is not None else self.qa
        effective_retry_limit = max(0, retry_limit) if retry_limit is not None else None

        for shot in sorted(shots, key=lambda item: item.index):
            continuity = self.bridge.shot_to_continuity(shot, assets=assets)
            prepared = self.director.prepare_shot(
                shot=shot,
                continuity=continuity,
                character_bibles=character_bibles,
                scene_bibles=scene_bibles,
            )
            compiled = self.compiler.compile_shot(
                provider=provider,
                director_dsl=prepared.director_dsl,
                continuity=prepared.continuity,
            )
            output_path = str(Path(output_dir) / f"{shot.id}.mp4")
            render_request = self.bridge.compile_render_request(
                shot,
                compiled,
                model=model,
                output_path=output_path,
            )
            metrics = (qa_metrics_by_shot or {}).get(shot.id)
            qa_report = qa_engine.evaluate(shot_id=shot.id, metrics=metrics)
            retry_request = None
            can_retry = auto_retry and (effective_retry_limit is None or len(retry_requests) < effective_retry_limit)
            if can_retry:
                retry_request = self.retry.build_retry_request(report=qa_report, compiled_prompt=compiled)
            if retry_request is not None:
                retry_requests.append(retry_request)
            render_requests.append(render_request)
            shot_plans.append(
                ShotPlan(
                    shot=shot,
                    continuity=prepared.continuity,
                    compiled_prompt=compiled,
                    render_request=render_request,
                    qa_report=qa_report,
                    retry_request=retry_request,
                )
            )

        post_plan = None
        if render_results:
            from .post_production import PostProductionPlanner

            post_planner = PostProductionPlanner()
            clips = post_planner.clips_from_shots(shots, render_results)
            post_plan = post_planner.plan_chapter(
                project_id=project.id,
                chapter_id=chapter.id,
                clips=clips,
                output_path=export_output_path or str(Path(output_dir).parent / "final.mp4"),
            )

        return ClosedLoopProductionPlan(
            project=project,
            chapter=chapter,
            workflow=workflow,
            shot_plans=shot_plans,
            render_requests=render_requests,
            qa_passed=all(item.qa_report.passed for item in shot_plans),
            retry_requests=retry_requests,
            metadata={
                "mode": "closed_loop_industrial_batch",
                "shot_count": len(shots),
                "retry_count": len(retry_requests),
                "provider": provider,
                "model": model,
                "qa_threshold": qa_threshold,
                "auto_retry": auto_retry,
                "retry_limit": retry_limit,
            },
            post_production_plan=post_plan,
        )
