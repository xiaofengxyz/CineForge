from __future__ import annotations

from .core import (
    JELLYFISH_FILM_WORKFLOW,
    CompiledPrompt,
    Entity,
    EntityRegistry,
    RenderRequest,
    ShotContinuityState,
    StudioAsset,
    StudioChapter,
    StudioProject,
    StudioShot,
    WorkflowGraph,
)


class StudioPlatformBridge:
    """Boundary adapter between Jellyfish Studio records and Film Core objects."""

    def register_assets(self, registry: EntityRegistry, assets: list[StudioAsset]) -> list[Entity]:
        entities: list[Entity] = []
        for asset in assets:
            entity = Entity(id=asset.id, kind=asset.kind)
            entity.add_component(
                "identity",
                {
                    "name": asset.name,
                    "description": asset.description,
                    "kind": asset.kind,
                },
            )
            entity.add_component("references", {"media": list(asset.reference_media)})
            entity.add_component("metadata", dict(asset.metadata))
            entities.append(registry.register(entity))
        return entities

    def shot_to_continuity(self, shot: StudioShot, *, assets: list[StudioAsset]) -> ShotContinuityState:
        assets_by_id = {asset.id: asset for asset in assets}
        refs = list(shot.reference_media)
        for character_id in shot.character_ids:
            refs.extend(assets_by_id.get(character_id, StudioAsset(character_id, "character", "")).reference_media)
        for prop_id in shot.prop_ids:
            refs.extend(assets_by_id.get(prop_id, StudioAsset(prop_id, "prop", "")).reference_media)
        for costume_id in shot.costume_ids:
            refs.extend(assets_by_id.get(costume_id, StudioAsset(costume_id, "costume", "")).reference_media)
        lighting = ""
        if shot.scene_id and shot.scene_id in assets_by_id:
            scene_asset = assets_by_id[shot.scene_id]
            refs.extend(scene_asset.reference_media)
            lighting = str(scene_asset.metadata.get("lighting") or "")
        return ShotContinuityState(
            shot_id=shot.id,
            character_ids=list(shot.character_ids),
            scene_id=shot.scene_id,
            prop_ids=list(shot.prop_ids),
            costume_ids=list(shot.costume_ids),
            outfit_map=dict(shot.metadata.get("outfit_map") or {}),
            emotion_map=dict(shot.metadata.get("emotion_map") or {}),
            lighting=lighting,
            timeline_position=f"chapter:{shot.chapter_id}:shot:{shot.index:04d}",
            reference_media=_dedupe(refs),
            metadata={"readiness_state": shot.readiness_state, **dict(shot.metadata)},
        )

    def build_chapter_workflow(
        self,
        project: StudioProject,
        chapter: StudioChapter,
        shots: list[StudioShot],
    ) -> WorkflowGraph:
        graph = WorkflowGraph()
        previous_id: str | None = None
        shot_ids = [shot.id for shot in sorted(shots, key=lambda item: item.index)]
        for index, system in enumerate(JELLYFISH_FILM_WORKFLOW):
            payload = {}
            if index == 0:
                payload = {
                    "project_id": project.id,
                    "chapter_id": chapter.id,
                    "shot_ids": shot_ids,
                }
            node = graph.add_node(
                system,
                node_id=f"{chapter.id}:{system}",
                payload=payload,
                depends_on=[previous_id] if previous_id else [],
            )
            previous_id = node.id
        return graph

    def compile_render_request(
        self,
        shot: StudioShot,
        compiled: CompiledPrompt,
        *,
        model: str,
        output_path: str,
    ) -> RenderRequest:
        parameters = dict(compiled.parameters)
        parameters["provider"] = compiled.provider
        parameters["negative_prompt"] = compiled.negative_text
        return RenderRequest(
            shot_id=shot.id,
            provider=compiled.provider,
            model=model,
            prompt=compiled.text,
            output_path=output_path,
            references=list(compiled.references),
            parameters=parameters,
        )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result

