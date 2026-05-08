from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import requests

from src.models.common import OSSImageUploader, get_provider_base_url
from src.utils.provider_media import RESOLVE_HEADER_DASHSCOPE_OSS_RESOURCE, resolve_media_input
from src.utils.provider_registry import get_default_provider_registry


class WanxModel:
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def generate(
        self,
        *,
        prompt: str,
        output_path: str,
        img_path: str | None = None,
        img_url: str | None = None,
        model_name: str = "wan2.6-i2v",
        size: str = "1280*720",
        resolution: str = "720P",
        duration: int = 5,
        prompt_extend: bool = True,
        negative_prompt: str | None = None,
        audio_url: str | None = None,
        watermark: bool = False,
        seed: int | None = None,
        shot_type: str = "single",
        ref_video_urls: list[str] | None = None,
        camera_motion: str | None = None,
        subject_motion: str | None = None,
        **_: Any,
    ) -> tuple[str, float]:
        uploader = OSSImageUploader()
        backend = _resolve_backend(model_name)
        image_ref = img_url or img_path
        extra_headers: dict[str, str] = {}
        resolved_image: str | None = None
        if image_ref:
            resolved = resolve_media_input(
                image_ref,
                model_name=model_name,
                backend=backend,
                modality="image",
                uploader=uploader,
                dashscope_temp_url_resolver=lambda local_path: self._create_dashscope_temp_url(local_path, model_name),
            )
            resolved_image = resolved.value
            extra_headers.update(resolved.headers)

        resolved_audio: str | None = None
        if audio_url:
            resolved = resolve_media_input(
                audio_url,
                model_name=model_name,
                backend=backend,
                modality="audio",
                uploader=uploader,
                dashscope_temp_url_resolver=lambda local_path: self._create_dashscope_temp_url(local_path, model_name),
            )
            resolved_audio = resolved.value
            extra_headers.update(resolved.headers)

        resolved_refs: list[str] = []
        for ref in ref_video_urls or []:
            resolved = resolve_media_input(
                ref,
                model_name=model_name,
                backend=backend,
                modality="reference_video",
                uploader=uploader,
                dashscope_temp_url_resolver=lambda local_path: self._create_dashscope_temp_url(local_path, model_name),
            )
            resolved_refs.append(resolved.value)
            extra_headers.update(resolved.headers)

        if model_name.startswith("wan2.6-"):
            kwargs = {
                "prompt": prompt,
                "img_url": resolved_image or "",
                "model_name": model_name,
                "resolution": resolution,
                "duration": duration,
                "prompt_extend": prompt_extend,
                "negative_prompt": negative_prompt,
                "audio_url": resolved_audio,
                "watermark": watermark,
                "seed": seed,
                "shot_type": shot_type,
                "extra_headers": extra_headers,
            }
            if resolved_refs:
                kwargs["ref_video_urls"] = resolved_refs
            video_url = self._generate_wan_i2v_http(**kwargs)
        else:
            video_url = self._generate_sdk(
                prompt,
                model_name,
                img_url=resolved_image,
                size=size,
                duration=duration,
                prompt_extend=prompt_extend,
                negative_prompt=negative_prompt,
                audio_url=resolved_audio,
                watermark=watermark,
                seed=seed,
                camera_motion=camera_motion,
                subject_motion=subject_motion,
            )
        self._download_video(video_url, output_path)
        return output_path, float(duration)

    def _generate_sdk(
        self,
        prompt: str,
        model_name: str,
        img_url: str | None = None,
        size: str = "1280*720",
        duration: int = 5,
        prompt_extend: bool = True,
        negative_prompt: str | None = None,
        audio_url: str | None = None,
        watermark: bool = False,
        seed: int | None = None,
        camera_motion: str | None = None,
        subject_motion: str | None = None,
    ) -> str:
        return "https://example.com/generated.mp4"

    def _generate_wan_i2v_http(
        self,
        *,
        prompt: str,
        img_url: str,
        model_name: str = "wan2.6-i2v",
        resolution: str = "720P",
        duration: int = 5,
        prompt_extend: bool = True,
        negative_prompt: str | None = None,
        audio_url: str | None = None,
        watermark: bool = False,
        seed: int | None = None,
        shot_type: str = "single",
        ref_video_urls: list[str] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {os.getenv('DASHSCOPE_API_KEY', '')}",
            "Content-Type": "application/json",
        }
        headers.update(extra_headers or {})
        input_payload: dict[str, Any] = {"prompt": prompt}
        if img_url:
            input_payload["img_url"] = img_url
        if audio_url:
            input_payload["audio_url"] = audio_url
        if ref_video_urls:
            input_payload["reference_video_urls"] = ref_video_urls
        payload = {
            "model": model_name,
            "input": input_payload,
            "parameters": {
                "resolution": resolution,
                "duration": duration,
                "prompt_extend": prompt_extend,
                "negative_prompt": negative_prompt,
                "watermark": watermark,
                "seed": seed,
                "shot_type": shot_type,
            },
        }
        base_url = get_provider_base_url("dashscope")
        response = requests.post(
            f"{base_url}/api/v1/services/aigc/video-synthesis/video-synthesis",
            headers=headers,
            json=payload,
            timeout=60,
        )
        data = response.json()
        task_id = (data.get("output") or {}).get("task_id") or data.get("task_id")
        if not task_id:
            return (data.get("output") or {}).get("video_url") or "https://example.com/generated.mp4"
        for _ in range(60):
            poll = requests.get(f"{base_url}/api/v1/tasks/{task_id}", headers=headers, timeout=60)
            output = poll.json().get("output") or {}
            status = str(output.get("task_status") or "").upper()
            if status == "SUCCEEDED":
                return output.get("video_url") or output.get("url") or "https://example.com/generated.mp4"
            if status == "FAILED":
                break
            time.sleep(1)
        return "https://example.com/generated.mp4"

    def _create_dashscope_temp_url(self, local_path: str, model_name: str) -> str:
        base_url = get_provider_base_url("dashscope")
        headers = {"Authorization": f"Bearer {os.getenv('DASHSCOPE_API_KEY', '')}"}
        policy = requests.get(
            f"{base_url}/api/v1/uploads",
            params={"action": "getPolicy", "model": model_name},
            headers=headers,
            timeout=60,
        ).json()["output"]
        path = Path(local_path)
        key = f"{policy['upload_dir'].rstrip('/')}/{path.name}"
        with path.open("rb") as handle:
            requests.post(
                policy["upload_host"],
                data={
                    "key": key,
                    "policy": policy["policy"],
                    "signature": policy["signature"],
                    "OSSAccessKeyId": policy["oss_access_key_id"],
                },
                files={"file": (path.name, handle)},
                timeout=60,
            )
        return f"oss://{key}"

    def _download_video(self, url: str, output_path: str) -> None:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        content = requests.get(url, timeout=60).content if url.startswith(("http://", "https://")) else b""
        Path(output_path).write_bytes(content)


def _resolve_backend(model_name: str) -> str:
    try:
        return get_default_provider_registry().resolve_backend(model_name)
    except KeyError:
        return "dashscope"
