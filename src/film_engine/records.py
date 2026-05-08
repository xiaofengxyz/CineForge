from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .core import StudioAsset, StudioChapter, StudioProject, StudioShot, StudioTask


def _ids_from_items(items: list[Any]) -> list[str]:
    ids: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            value = item.get("id")
        else:
            value = item
        if value:
            ids.append(str(value))
    return ids


@dataclass
class JellyfishShotBundle:
    project: dict[str, Any]
    chapter: dict[str, Any]
    shot: dict[str, Any]
    detail: dict[str, Any] = field(default_factory=dict)
    asset_overview: list[dict[str, Any]] = field(default_factory=list)
    dialogue_lines: list[dict[str, Any]] = field(default_factory=list)
    frame_images: list[dict[str, Any]] = field(default_factory=list)


class JellyfishRecordMapper:
    def project(self, record: dict[str, Any]) -> StudioProject:
        known = {"id", "name", "title", "description", "style", "visual_style", "chapters"}
        metadata = {key: value for key, value in record.items() if key not in known}
        return StudioProject(
            id=str(record.get("id", "")),
            title=str(record.get("title") or record.get("name") or ""),
            description=str(record.get("description") or ""),
            style=record.get("style"),
            visual_style=record.get("visual_style"),
            chapter_ids=_ids_from_items(record.get("chapters") or []),
            metadata=metadata,
        )

    def chapter(self, record: dict[str, Any]) -> StudioChapter:
        known = {
            "id",
            "project_id",
            "index",
            "order",
            "title",
            "raw_text",
            "condensed_text",
            "shots",
        }
        metadata = {key: value for key, value in record.items() if key not in known}
        return StudioChapter(
            id=str(record.get("id", "")),
            project_id=str(record.get("project_id", "")),
            title=str(record.get("title") or ""),
            order=int(record.get("order") or record.get("index") or 1),
            shot_ids=_ids_from_items(record.get("shots") or []),
            raw_text=str(record.get("raw_text") or ""),
            condensed_text=str(record.get("condensed_text") or ""),
            metadata=metadata,
        )

    def asset(self, record: dict[str, Any]) -> StudioAsset:
        refs: list[str] = []
        if record.get("thumbnail"):
            refs.append(str(record["thumbnail"]))
        for image in record.get("images") or []:
            if isinstance(image, dict) and image.get("file_id"):
                refs.append(str(image["file_id"]))
            elif image:
                refs.append(str(image))
        metadata = {
            key: value
            for key, value in record.items()
            if key not in {"id", "type", "kind", "name", "description", "thumbnail", "images"}
        }
        return StudioAsset(
            id=str(record.get("id", "")),
            kind=str(record.get("kind") or record.get("type") or "asset"),
            name=str(record.get("name") or ""),
            description=str(record.get("description") or ""),
            reference_media=refs,
            metadata=metadata,
        )

    def shot_bundle(self, bundle: JellyfishShotBundle) -> StudioShot:
        shot = bundle.shot
        detail = bundle.detail
        character_ids: list[str] = []
        prop_ids: list[str] = []
        costume_ids: list[str] = []
        for item in bundle.asset_overview:
            if not item.get("is_linked", True):
                continue
            entity_id = item.get("linked_entity_id") or item.get("id")
            if not entity_id:
                continue
            item_type = str(item.get("type") or item.get("kind") or "")
            if item_type == "character":
                character_ids.append(str(entity_id))
            elif item_type == "prop":
                prop_ids.append(str(entity_id))
            elif item_type == "costume":
                costume_ids.append(str(entity_id))

        refs: list[str] = []
        for key in ("thumbnail", "generated_video_file_id"):
            if shot.get(key):
                refs.append(str(shot[key]))
        for frame in bundle.frame_images:
            file_id = frame.get("file_id") if isinstance(frame, dict) else None
            if file_id:
                refs.append(str(file_id))

        dialogue = [
            str(item.get("text") or "")
            for item in sorted(bundle.dialogue_lines, key=lambda row: int(row.get("index") or 0))
            if item.get("text")
        ]
        status = str(shot.get("status") or "")
        return StudioShot(
            id=str(shot.get("id", "")),
            project_id=str(bundle.project.get("id", "")),
            chapter_id=str(shot.get("chapter_id") or bundle.chapter.get("id") or ""),
            index=int(shot.get("index") or 1),
            title=str(shot.get("title") or ""),
            summary=str(shot.get("script_excerpt") or shot.get("summary") or ""),
            scene_id=detail.get("scene_id"),
            character_ids=character_ids,
            prop_ids=prop_ids,
            costume_ids=costume_ids,
            dialogue=dialogue,
            camera={
                "framing": detail.get("camera_shot"),
                "angle": detail.get("angle"),
                "movement": detail.get("movement"),
                "emotion": detail.get("mood_tags"),
                "atmosphere": detail.get("atmosphere"),
                "ratio": detail.get("override_video_ratio"),
                "action_beats": detail.get("action_beats") or [],
            },
            duration=float(detail["duration"]) if detail.get("duration") is not None else None,
            reference_media=refs,
            readiness_state=status,
            is_generation_ready=status == "ready",
            metadata={
                "jellyfish_status": status,
                "extraction": shot.get("extraction"),
            },
        )

    def task(self, record: dict[str, Any], *, project_id: str) -> StudioTask:
        result_media: list[str] = []
        result = record.get("result") if isinstance(record.get("result"), dict) else {}
        if result.get("file_id"):
            result_media.append(str(result["file_id"]))
        relation_type = str(record.get("relation_type") or "")
        shot_id = str(record.get("relation_entity_id") or "") if relation_type == "shot" else None
        return StudioTask(
            id=str(record.get("task_id") or record.get("id") or ""),
            project_id=project_id,
            shot_id=shot_id,
            task_type=str(record.get("task_kind") or record.get("type") or ""),
            status=str(record.get("status") or ""),
            result_media=result_media,
            metadata={
                "progress": record.get("progress"),
                "relation_type": relation_type,
                "resource_type": record.get("resource_type"),
            },
        )

