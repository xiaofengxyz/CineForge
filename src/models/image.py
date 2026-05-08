from __future__ import annotations

import os
import time
from typing import Any

import requests

from src.models.common import OSSImageUploader, get_provider_base_url
from src.utils.provider_media import resolve_media_input
from src.utils.provider_registry import get_default_provider_registry


def resolve_provider_backend(model_name: str) -> str:
    return get_default_provider_registry().resolve_backend(model_name)


class WanxImageModel:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def _resolve_wan26_reference_image(self, ref: str, *, model_name: str | None = None) -> str:
        effective_model = model_name or (self.config.get("params") or {}).get("i2i_model_name") or "wan2.6-image"
        try:
            backend = resolve_provider_backend(effective_model)
        except KeyError:
            backend = "dashscope"
        resolved = resolve_media_input(
            ref,
            model_name=effective_model,
            backend=backend,
            modality="image",
            uploader=OSSImageUploader(),
        )
        return resolved.value

    def _generate_wan26_image_http(
        self,
        *,
        prompt: str,
        size: str = "1280*1280",
        n: int = 1,
        negative_prompt: str | None = None,
        ref_image_paths: list[str] | None = None,
    ) -> str:
        content = [{"image": self._resolve_wan26_reference_image(ref)} for ref in ref_image_paths or []]
        content.append({"text": prompt})
        payload = {
            "model": (self.config.get("params") or {}).get("i2i_model_name", "wan2.6-image"),
            "input": {"messages": [{"role": "user", "content": content}]},
            "parameters": {"size": size, "n": n, "negative_prompt": negative_prompt},
        }
        headers = {"Authorization": f"Bearer {os.getenv('DASHSCOPE_API_KEY', '')}"}
        base_url = get_provider_base_url("dashscope")
        response = requests.post(f"{base_url}/api/v1/services/aigc/multimodal-generation/generation", headers=headers, json=payload, timeout=60)
        task_id = (response.json().get("output") or {}).get("task_id")
        if not task_id:
            return _extract_image(response.json())
        for _ in range(60):
            poll = requests.get(f"{base_url}/api/v1/tasks/{task_id}", headers=headers, timeout=60)
            output = poll.json().get("output") or {}
            if str(output.get("task_status") or "").upper() == "SUCCEEDED":
                return _extract_image({"output": output})
            time.sleep(1)
        return ""


def _extract_image(payload: dict[str, Any]) -> str:
    output = payload.get("output") or {}
    choices = output.get("choices") or []
    if choices:
        content = ((choices[0].get("message") or {}).get("content") or [])
        for item in content:
            if item.get("image"):
                return item["image"]
    return output.get("image_url") or ""

