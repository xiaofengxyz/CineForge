from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

from src.models.common import OSSImageUploader
from src.utils.provider_media import resolve_media_input


class ViduModel:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def generate(
        self,
        *,
        prompt: str,
        output_path: str,
        img_path: str | None = None,
        img_url: str | None = None,
        model: str = "viduq3-pro",
        audio: bool | None = None,
        movement_amplitude: str | None = None,
        seed: int | None = None,
        **_: Any,
    ) -> tuple[str, float]:
        image = img_url
        if img_path:
            image = resolve_media_input(
                img_path,
                model_name=model,
                backend="vendor",
                modality="image",
                uploader=OSSImageUploader(),
            ).value
        body: dict[str, Any] = {"prompt": prompt, "model": model}
        if image:
            body["images"] = [image]
        if audio is not None:
            body["audio"] = audio
        if movement_amplitude is not None:
            body["movement_amplitude"] = movement_amplitude
        if seed is not None:
            body["seed"] = seed

        response = requests.post(
            "https://api.vidu.example/ent/v2/img2video",
            headers={"Authorization": f"Token {self.config.get('api_key', '')}"},
            json=body,
            timeout=60,
        )
        task_id = response.json().get("task_id") or (response.json().get("data") or {}).get("task_id")
        video_url = ""
        for _ in range(60):
            poll = requests.get(f"https://api.vidu.example/ent/v2/tasks/{task_id}", headers={"Authorization": f"Token {self.config.get('api_key', '')}"}, timeout=60)
            data = poll.json()
            if str(data.get("state") or data.get("status") or "").lower() in {"success", "succeed"}:
                creations = data.get("creations") or []
                video_url = creations[0].get("url") if creations else data.get("url", "")
                break
            time.sleep(1)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(requests.get(video_url, timeout=60).content if video_url else b"")
        return output_path, 0.0

