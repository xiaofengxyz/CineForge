from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import requests


class KlingModel:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def generate(
        self,
        *,
        prompt: str,
        output_path: str,
        img_path: str | None = None,
        img_url: str | None = None,
        model: str = "kling-v1",
        mode: str | None = None,
        sound: str | None = None,
        cfg_scale: float | None = None,
        seed: int | None = None,
        **_: Any,
    ) -> tuple[str, float]:
        body: dict[str, Any] = {"prompt": prompt, "model": model}
        image_value = img_url
        if img_path:
            image_value = _local_image_to_base64(img_path)
        if image_value:
            body["image"] = image_value
        if mode is not None:
            body["mode"] = mode
        if sound is not None:
            body["sound"] = sound
        if cfg_scale is not None:
            body["cfg_scale"] = cfg_scale
        if seed is not None:
            body["seed"] = seed

        endpoint = "https://api.klingai.example/v1/videos/image2video" if image_value else "https://api.klingai.example/v1/videos/text2video"
        response = requests.post(endpoint, headers={"Authorization": "Bearer local-test-token"}, json=body, timeout=60)
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        task_id = ((response.json().get("data") or {}).get("task_id")) or response.json().get("task_id")
        video_url = ""
        for _ in range(60):
            poll = requests.get(f"{endpoint}/{task_id}", headers={"Authorization": "Bearer local-test-token"}, timeout=60)
            if hasattr(poll, "raise_for_status"):
                poll.raise_for_status()
            data = poll.json().get("data") or poll.json()
            if str(data.get("task_status") or data.get("status") or "").lower() in {"succeed", "success"}:
                videos = ((data.get("task_result") or {}).get("videos") or data.get("videos") or [])
                video_url = videos[0].get("url") if videos else data.get("url", "")
                break
            time.sleep(1)
        _download(video_url, output_path)
        return output_path, 0.0


def _local_image_to_base64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def _download(url: str, output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    content = requests.get(url, timeout=60).content if url else b""
    Path(output_path).write_bytes(content)

