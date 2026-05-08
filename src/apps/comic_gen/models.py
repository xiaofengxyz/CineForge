from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProviderBackend(str, Enum):
    DASHSCOPE = "dashscope"
    VENDOR = "vendor"


class ProviderRoutingConfig(BaseModel):
    KLING_PROVIDER_MODE: ProviderBackend = ProviderBackend.DASHSCOPE
    VIDU_PROVIDER_MODE: ProviderBackend = ProviderBackend.DASHSCOPE
    PIXVERSE_PROVIDER_MODE: ProviderBackend = ProviderBackend.DASHSCOPE

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_backend(cls, value: Any) -> ProviderBackend:
        if isinstance(value, ProviderBackend):
            return value
        if str(value or "").lower() == "vendor":
            return ProviderBackend.VENDOR
        return ProviderBackend.DASHSCOPE


class PromptConfig(BaseModel):
    storyboard_polish: str = ""
    video_polish: str = ""
    r2v_polish: str = ""


class ModelSettings(BaseModel):
    t2i_model: str = "wan2.6-t2i"
    i2i_model: str = "wan2.6-image"
    i2v_model: str = "wan2.6-i2v"
    storyboard_aspect_ratio: str = "16:9"
    video_resolution: str = "720P"


class Character(BaseModel):
    id: str
    name: str
    description: str = ""
    image_url: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Scene(BaseModel):
    id: str
    name: str
    description: str = ""
    image_url: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Prop(BaseModel):
    id: str
    name: str
    description: str = ""
    image_url: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoryboardFrame(BaseModel):
    id: str
    scene_id: str
    character_ids: list[str] = Field(default_factory=list)
    prop_ids: list[str] = Field(default_factory=list)
    rendered_image_url: str = ""
    prompt: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class VideoTask(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    project_id: str
    image_url: str
    prompt: str
    status: str = "pending"
    video_url: str = ""
    model: str = "wan2.6-i2v"
    duration: int | None = None
    seed: int | None = None
    resolution: str | None = None
    generate_audio: bool | None = None
    prompt_extend: bool | None = None
    negative_prompt: str | None = None
    shot_type: str | None = None
    generation_mode: str | None = None
    mode: str | None = None
    sound: str | None = None
    cfg_scale: float | None = None
    vidu_audio: bool | None = None
    movement_amplitude: str | None = None


class Script(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    original_text: str
    characters: list[Character] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    props: list[Prop] = Field(default_factory=list)
    frames: list[StoryboardFrame] = Field(default_factory=list)
    video_tasks: list[VideoTask] = Field(default_factory=list)
    prompt_config: PromptConfig = Field(default_factory=PromptConfig)
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    series_id: str | None = None
    episode_number: int | None = None
    created_at: float
    updated_at: float


class Series(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    description: str = ""
    characters: list[Character] = Field(default_factory=list)
    scenes: list[Scene] = Field(default_factory=list)
    props: list[Prop] = Field(default_factory=list)
    art_direction: str | None = None
    prompt_config: PromptConfig = Field(default_factory=PromptConfig)
    model_settings: ModelSettings = Field(default_factory=ModelSettings)
    episode_ids: list[str] = Field(default_factory=list)
    created_at: float
    updated_at: float

