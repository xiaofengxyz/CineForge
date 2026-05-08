from __future__ import annotations

from pydantic import BaseModel


class CreateVideoTaskRequest(BaseModel):
    image_url: str
    prompt: str
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

