from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class ProviderFamilyConfig:
    model_family: str
    backend_default: str
    backend_env_key: str | None = None
    credential_sources: dict[str, tuple[str, ...]] = field(default_factory=dict)
    supported_modalities: tuple[str, ...] = ()
    image_input_mode: dict[str, str] = field(default_factory=dict)
    audio_input_mode: dict[str, str] = field(default_factory=dict)
    reference_video_input_mode: dict[str, str] = field(default_factory=dict)


class ProviderRegistry:
    def __init__(self) -> None:
        self._families: list[ProviderFamilyConfig] = []

    def register_family(self, config: ProviderFamilyConfig) -> None:
        self._families.append(config)

    def resolve_family(self, model_name: str) -> ProviderFamilyConfig:
        for family in self._families:
            if model_name.startswith(family.model_family):
                return family
        raise KeyError(f"Unknown provider family for model: {model_name}")

    def resolve_backend(self, model_name: str, env: dict[str, str] | None = None) -> str:
        family = self.resolve_family(model_name)
        source = env if env is not None else os.environ
        configured = ""
        if family.backend_env_key:
            configured = str(source.get(family.backend_env_key, "") or "").strip().lower()
        if configured in family.credential_sources:
            return configured
        if configured in {"dashscope", "vendor"}:
            return configured if configured in family.credential_sources else family.backend_default
        return family.backend_default


def get_default_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register_family(
        ProviderFamilyConfig(
            model_family="wan2.6-",
            backend_default="dashscope",
            backend_env_key="DASHSCOPE_PROVIDER_MODE",
            credential_sources={"dashscope": ("DASHSCOPE_API_KEY",)},
            supported_modalities=("t2i", "i2i", "i2v", "r2v"),
        )
    )
    registry.register_family(
        ProviderFamilyConfig(
            model_family="kling",
            backend_default="dashscope",
            backend_env_key="KLING_PROVIDER_MODE",
            credential_sources={
                "dashscope": ("DASHSCOPE_API_KEY",),
                "vendor": ("KLING_ACCESS_KEY", "KLING_SECRET_KEY"),
            },
            supported_modalities=("t2v", "i2v"),
        )
    )
    registry.register_family(
        ProviderFamilyConfig(
            model_family="vidu",
            backend_default="dashscope",
            backend_env_key="VIDU_PROVIDER_MODE",
            credential_sources={
                "dashscope": ("DASHSCOPE_API_KEY",),
                "vendor": ("VIDU_API_KEY",),
            },
            supported_modalities=("t2v", "i2v"),
        )
    )
    registry.register_family(
        ProviderFamilyConfig(
            model_family="pixverse-",
            backend_default="dashscope",
            backend_env_key="PIXVERSE_PROVIDER_MODE",
            credential_sources={
                "dashscope": ("DASHSCOPE_API_KEY",),
                "vendor": ("PIXVERSE_API_KEY",),
            },
            supported_modalities=("t2v", "i2v"),
        )
    )
    return registry

