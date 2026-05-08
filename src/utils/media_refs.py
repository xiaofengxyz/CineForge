from __future__ import annotations

import os
from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def is_remote_media_ref(value: str) -> bool:
    return value.startswith(("http://", "https://", "blob:"))


def is_stable_project_media_ref(value: str) -> bool:
    if value.startswith("blob:"):
        return False
    return classify_media_ref(value) in {"local_path", "object_key", "remote_url"}


def classify_media_ref(value: str) -> str:
    if value.startswith("data:"):
        return "data_uri"
    if is_remote_media_ref(value):
        return "remote_url"
    base = os.getenv("OSS_BASE_PATH", "").strip("/")
    if (base and value.startswith(f"{base}/")) or value.startswith("lumenx/"):
        return "object_key"
    return "local_path"


def resolve_local_media_path(value: str, *, root: str | Path | None = None) -> str:
    path = Path(value)
    if path.is_absolute():
        return str(path.resolve())
    base = Path(root) if root is not None else project_root()
    if path.parts and path.parts[0] == "output":
        return str((base / path).resolve())
    return str((base / "output" / value).resolve())
