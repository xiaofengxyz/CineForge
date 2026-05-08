from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .media_refs import classify_media_ref, is_remote_media_ref, resolve_local_media_path


RESOLVE_HEADER_DASHSCOPE_OSS_RESOURCE = "X-DashScope-OssResourceResolve"


@dataclass
class ResolvedMediaInput:
    value: str
    headers: dict[str, str] = field(default_factory=dict)


def resolve_media_inputs(refs: list[str], **kwargs: object) -> list[ResolvedMediaInput]:
    return [resolve_media_input(ref, **kwargs) for ref in list(refs)]


def resolve_media_input(
    ref: str,
    *,
    model_name: str,
    backend: str,
    modality: str,
    uploader: object,
    project_root: str | None = None,
    dashscope_temp_url_resolver: Callable[[str], str] | None = None,
) -> ResolvedMediaInput:
    kind = classify_media_ref(ref)
    if kind in {"remote_url", "data_uri"}:
        return ResolvedMediaInput(ref)
    if kind == "object_key":
        if getattr(uploader, "is_configured", False):
            return ResolvedMediaInput(uploader.sign_url_for_api(ref))
        return ResolvedMediaInput(ref)

    local_path = resolve_local_media_path(ref, root=project_root) if not Path(ref).is_absolute() else str(Path(ref).resolve())
    if backend == "dashscope":
        if getattr(uploader, "is_configured", False):
            object_key = uploader.upload_file(local_path, sub_path="temp/provider_media")
            return ResolvedMediaInput(uploader.sign_url_for_api(object_key))
        if modality == "image" and not model_name.startswith(("wan2.6-i2v", "wan2.6-r2v")):
            return ResolvedMediaInput(_file_to_data_uri(local_path))
        if dashscope_temp_url_resolver is None:
            raise ValueError(f"{modality} local media requires OSS or a dashscope_temp_url_resolver")
        return ResolvedMediaInput(
            dashscope_temp_url_resolver(local_path),
            headers={RESOLVE_HEADER_DASHSCOPE_OSS_RESOURCE: "enable"},
        )

    if backend == "vendor":
        if model_name.startswith("kling") and modality == "image":
            return ResolvedMediaInput(_file_to_base64(local_path))
        if model_name.startswith("vidu"):
            if getattr(uploader, "is_configured", False):
                object_key = uploader.upload_file(local_path, sub_path="temp/provider_media")
                return ResolvedMediaInput(uploader.sign_url_for_api(object_key))
            raise ValueError("Vidu vendor adapter requires a URL-compatible media source")
        if getattr(uploader, "is_configured", False):
            object_key = uploader.upload_file(local_path, sub_path="temp/provider_media")
            return ResolvedMediaInput(uploader.sign_url_for_api(object_key))
    return ResolvedMediaInput(ref)


def _file_to_base64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def _file_to_data_uri(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return f"data:{mime or 'application/octet-stream'};base64,{_file_to_base64(path)}"
