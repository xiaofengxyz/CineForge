from __future__ import annotations

import os
from pathlib import Path


class OSSImageUploader:
    def __init__(self) -> None:
        self.is_configured = all(
            os.getenv(key)
            for key in ("ALIBABA_CLOUD_ACCESS_KEY_ID", "ALIBABA_CLOUD_ACCESS_KEY_SECRET", "OSS_BUCKET_NAME")
        )
        self.base_path = os.getenv("OSS_BASE_PATH", "lumenx").strip("/")

    def upload_file(self, local_path: str, sub_path: str = "", custom_filename: str | None = None) -> str | None:
        if not self.is_configured:
            return None
        filename = custom_filename or Path(local_path).name
        return f"{self.base_path}/{sub_path.strip('/')}/{filename}".replace("//", "/")

    def sign_url_for_api(self, object_key: str) -> str:
        endpoint = os.getenv("OSS_PUBLIC_ENDPOINT", "https://oss.example")
        return f"{endpoint.rstrip('/')}/{object_key.lstrip('/')}"


def get_provider_base_url(provider: str) -> str:
    if provider == "dashscope":
        return os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com")
    return ""

