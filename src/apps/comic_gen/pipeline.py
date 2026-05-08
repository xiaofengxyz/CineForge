from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from .llm import (
    DEFAULT_R2V_POLISH_PROMPT,
    DEFAULT_STORYBOARD_POLISH_PROMPT,
    DEFAULT_VIDEO_POLISH_PROMPT,
)
from .models import Character, Prop, Scene, Script, Series, VideoTask
from src.utils.media_refs import is_remote_media_ref, resolve_local_media_path
from src.utils.provider_registry import get_default_provider_registry


class ScriptProcessor: ...
class AssetGenerator: ...
class StoryboardGenerator: ...
class VideoGenerator: ...
class AudioGenerator: ...
class ExportManager: ...


DEFAULT_PROMPTS = {
    "storyboard_polish": DEFAULT_STORYBOARD_POLISH_PROMPT,
    "video_polish": DEFAULT_VIDEO_POLISH_PROMPT,
    "r2v_polish": DEFAULT_R2V_POLISH_PROMPT,
}


class ComicGenPipeline:
    def __init__(self) -> None:
        self.scripts: dict[str, Script] = {}
        self.series_store: dict[str, Series] = {}
        self.data_file = "projects.json"
        self.series_data_file = "series.json"
        self.video_generator = VideoGenerator()
        self._kling_model = None
        self._vidu_model = None

    def _save_data(self) -> None:
        return

    def _save_series(self) -> None:
        return

    def create_series(self, title: str, description: str = "") -> Series:
        now = time.time()
        series = Series(id=str(uuid.uuid4()), title=title, description=description, created_at=now, updated_at=now)
        self.series_store[series.id] = series
        self._save_series()
        return series

    def get_series(self, series_id: str) -> Series | None:
        return self.series_store.get(series_id)

    def list_series(self) -> list[Series]:
        return list(self.series_store.values())

    def update_series(self, series_id: str, updates: dict[str, Any]) -> Series:
        series = self.get_series(series_id)
        if series is None:
            raise ValueError("Series not found")
        protected = {"id", "created_at", "episode_ids"}
        for key, value in updates.items():
            if key in protected:
                continue
            if hasattr(series, key):
                setattr(series, key, value)
        series.updated_at = time.time()
        self._save_series()
        return series

    def delete_series(self, series_id: str) -> None:
        series = self.get_series(series_id)
        if series is None:
            raise ValueError("Series not found")
        for episode_id in list(series.episode_ids):
            episode = self.scripts.get(episode_id)
            if episode:
                episode.series_id = None
                episode.episode_number = None
        del self.series_store[series_id]
        self._save_series()

    def get_script(self, script_id: str) -> Script | None:
        return self.scripts.get(script_id)

    def add_episode_to_series(self, series_id: str, episode_id: str, episode_number: int | None = None) -> Series:
        series = self.get_series(series_id)
        episode = self.scripts.get(episode_id)
        if series is None:
            raise ValueError("Series not found")
        if episode is None:
            raise ValueError("Episode not found")
        if episode.series_id and episode.series_id in self.series_store:
            old_series = self.series_store[episode.series_id]
            old_series.episode_ids = [item for item in old_series.episode_ids if item != episode_id]
        if episode_id not in series.episode_ids:
            series.episode_ids.append(episode_id)
        episode.series_id = series.id
        episode.episode_number = episode_number or len(series.episode_ids)
        episode.updated_at = time.time()
        series.updated_at = time.time()
        self._save_data()
        self._save_series()
        return series

    def remove_episode_from_series(self, series_id: str, episode_id: str) -> Series:
        series = self.get_series(series_id)
        if series is None:
            raise ValueError("Series not found")
        series.episode_ids = [item for item in series.episode_ids if item != episode_id]
        episode = self.scripts.get(episode_id)
        if episode:
            episode.series_id = None
            episode.episode_number = None
        series.updated_at = time.time()
        self._save_data()
        return series

    def get_series_episodes(self, series_id: str) -> list[Script]:
        series = self.get_series(series_id)
        if series is None:
            raise ValueError("Series not found")
        episodes = [self.scripts[item] for item in series.episode_ids if item in self.scripts]
        return sorted(episodes, key=lambda item: (item.episode_number or 10**9, item.created_at))

    def resolve_episode_assets(self, episode: Script, series: Series | None = None) -> dict[str, list[Any]]:
        resolved_series = series or (self.series_store.get(episode.series_id) if episode.series_id else None)
        return {
            "characters": _merge_assets(resolved_series.characters if resolved_series else [], episode.characters),
            "scenes": _merge_assets(resolved_series.scenes if resolved_series else [], episode.scenes),
            "props": _merge_assets(resolved_series.props if resolved_series else [], episode.props),
        }

    def get_effective_prompt(self, prompt_type: str, episode: Script, series: Series | None = None) -> str:
        if prompt_type not in DEFAULT_PROMPTS:
            raise ValueError(f"Invalid prompt_type: {prompt_type}")
        episode_value = getattr(episode.prompt_config, prompt_type, "")
        if episode_value and episode_value.strip():
            return episode_value
        resolved_series = series or (self.series_store.get(episode.series_id) if episode.series_id else None)
        if resolved_series is not None:
            series_value = getattr(resolved_series.prompt_config, prompt_type, "")
            if series_value and series_value.strip():
                return series_value
        return DEFAULT_PROMPTS[prompt_type]

    def _split_text_by_markers(self, text: str, episodes_data: list[dict[str, str]]) -> list[str]:
        count = len(episodes_data)
        if count == 0:
            return []
        if not text:
            return [""] * count
        if all(not (item.get("start_marker") or item.get("end_marker")) for item in episodes_data):
            return _equal_split(text, count)
        chunks: list[str] = []
        cursor = 0
        for item in episodes_data:
            start_marker = item.get("start_marker") or ""
            end_marker = item.get("end_marker") or ""
            start = text.find(start_marker, cursor) if start_marker else cursor
            if start < 0:
                return _equal_split(text, count)
            if end_marker:
                end_pos = text.find(end_marker, start + len(start_marker))
                if end_pos < 0:
                    return _equal_split(text, count)
                end = end_pos + len(end_marker)
            else:
                end = len(text)
            chunks.append(text[start:end])
            cursor = end
        if len(chunks) != count:
            return _equal_split(text, count)
        return chunks

    def import_assets_from_series(
        self,
        target_series_id: str,
        source_series_id: str,
        asset_ids: list[str],
    ) -> tuple[Series, list[str], list[str]]:
        target = self.get_series(target_series_id)
        source = self.get_series(source_series_id)
        if target is None or source is None:
            raise ValueError("Series not found")
        imported: list[str] = []
        skipped: list[str] = []
        for asset_id in asset_ids:
            found = _find_asset(source, asset_id)
            if found is None:
                skipped.append(asset_id)
                continue
            kind, asset = found
            copied = asset.model_copy(deep=True)
            copied.id = str(uuid.uuid4())
            getattr(target, kind).append(copied)
            imported.append(asset_id)
        target.updated_at = time.time()
        self._save_series()
        return target, imported, skipped

    def _download_temp_image(self, image_url: str) -> str:
        return image_url

    def create_video_task(self, *, script_id: str, image_url: str, prompt: str, **kwargs: Any) -> tuple[Script, str]:
        script = self.get_script(script_id)
        if script is None:
            raise ValueError("Script not found")
        task_id = str(uuid.uuid4())
        stable_image_url = self._snapshot_video_input(image_url, task_id)
        task = VideoTask(id=task_id, project_id=script_id, image_url=stable_image_url, prompt=prompt, **kwargs)
        script.video_tasks.append(task)
        script.updated_at = time.time()
        self._save_data()
        return script, task_id

    def process_video_task(self, script_id: str, task_id: str) -> None:
        script = self.get_script(script_id)
        if script is None:
            raise ValueError("Script not found")
        task = next((item for item in script.video_tasks if item.id == task_id), None)
        if task is None:
            raise ValueError("Video task not found")
        img_path = self._download_temp_image(task.image_url) if is_remote_media_ref(task.image_url) else resolve_local_media_path(task.image_url)
        output_rel = f"video/video_{task.id}.mp4"
        output_path = str(Path("output") / output_rel)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        registry = get_default_provider_registry()
        backend = registry.resolve_backend(task.model)
        if task.model.startswith("kling") and backend == "vendor":
            from src.models.kling import KlingModel

            model = self._kling_model or KlingModel({})
            result_path, _ = model.generate(
                prompt=task.prompt,
                output_path=output_path,
                img_path=img_path,
                model=task.model,
                mode=task.mode,
                sound=task.sound,
                cfg_scale=task.cfg_scale,
                seed=task.seed,
            )
        elif task.model.startswith("vidu") and backend == "vendor":
            from src.models.vidu import ViduModel

            model = self._vidu_model or ViduModel({})
            result_path, _ = model.generate(
                prompt=task.prompt,
                output_path=output_path,
                img_path=img_path,
                model=task.model,
                audio=task.vidu_audio,
                movement_amplitude=task.movement_amplitude,
                seed=task.seed,
            )
        else:
            model = self.video_generator.model
            result_path, _ = model.generate(
                prompt=task.prompt,
                output_path=output_path,
                img_path=img_path,
                model=task.model,
                model_name=task.model,
                duration=task.duration or 5,
                resolution=task.resolution or "720P",
                prompt_extend=True if task.prompt_extend is None else task.prompt_extend,
                negative_prompt=task.negative_prompt,
                seed=task.seed,
                shot_type=task.shot_type or "single",
            )
        task.status = "completed"
        task.video_url = output_rel if str(result_path).startswith("output") else output_rel
        script.updated_at = time.time()
        self._save_data()

    def _snapshot_video_input(self, image_url: str, task_id: str) -> str:
        if is_remote_media_ref(image_url):
            return image_url
        source = Path(resolve_local_media_path(image_url))
        if not source.exists():
            return image_url
        suffix = source.suffix or ".png"
        rel = f"video_inputs/{task_id}{suffix}"
        target = Path("output") / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        return rel


def _merge_assets(series_assets: list[Any], episode_assets: list[Any]) -> list[Any]:
    merged = {item.id: item for item in series_assets}
    for item in episode_assets:
        merged[item.id] = item
    return list(merged.values())


def _find_asset(series: Series, asset_id: str) -> tuple[str, Character | Scene | Prop] | None:
    for kind in ("characters", "scenes", "props"):
        for asset in getattr(series, kind):
            if asset.id == asset_id:
                return kind, asset
    return None


def _equal_split(text: str, count: int) -> list[str]:
    base = len(text) // count
    rem = len(text) % count
    chunks: list[str] = []
    cursor = 0
    for index in range(count):
        size = base + (1 if index < rem else 0)
        chunks.append(text[cursor:cursor + size])
        cursor += size
    return chunks
