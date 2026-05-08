from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .core import RenderResult, StudioShot


@dataclass
class DialogueCue:
    shot_id: str
    speaker_name: str
    text: str
    start: float
    end: float


class DialogueNormalizer:
    def parse(self, *, shot_id: str, line: str, duration: float) -> DialogueCue | None:
        raw = (line or "").strip()
        if not raw or ":" not in raw:
            return None
        speaker, text = [part.strip() for part in raw.split(":", 1)]
        if not text or speaker.lower() in {"ambient", "sfx", "bgm"}:
            return None
        start = 0.5
        end = max(start + 0.5, float(duration) - 0.5)
        return DialogueCue(shot_id=shot_id, speaker_name=speaker, text=text, start=start, end=end)


@dataclass
class PostProductionClip:
    shot_id: str
    video_path: str
    duration: float
    dialogue: list[DialogueCue] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PostProductionStep:
    id: str
    system: str
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)


@dataclass
class PostProductionPlan:
    project_id: str
    chapter_id: str
    steps: list[PostProductionStep]
    output_path: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def steps_by_system(self, system: str) -> list[PostProductionStep]:
        return [step for step in self.steps if step.system == system]


class SubtitleCompiler:
    def cues_for_clip(self, clip: PostProductionClip) -> list[DialogueCue]:
        return list(clip.dialogue)

    def to_srt(self, cues: list[DialogueCue]) -> str:
        blocks: list[str] = []
        for index, cue in enumerate(cues, start=1):
            blocks.append(
                f"{index}\n{_format_ts(cue.start)} --> {_format_ts(cue.end)}\n{cue.text}\n"
            )
        return "\n".join(blocks)


class PostProductionPlanner:
    def __init__(self) -> None:
        self.dialogue_normalizer = DialogueNormalizer()

    def plan_chapter(
        self,
        *,
        project_id: str,
        chapter_id: str,
        clips: list[PostProductionClip],
        output_path: str,
        work_dir: str = "output/post",
        tts_provider: str = "local",
    ) -> PostProductionPlan:
        steps: list[PostProductionStep] = []
        compose_ids: list[str] = []
        for clip in clips:
            audio_path = f"{work_dir}/{clip.shot_id}.mp3"
            subtitle_path = f"{work_dir}/{clip.shot_id}.srt"
            depends: list[str] = []
            if clip.dialogue:
                tts_id = f"{chapter_id}:{clip.shot_id}:tts"
                subtitle_id = f"{chapter_id}:{clip.shot_id}:subtitle"
                steps.append(
                    PostProductionStep(
                        id=tts_id,
                        system="tts",
                        inputs={"provider": tts_provider, "dialogue": [cue.text for cue in clip.dialogue]},
                        outputs={"audio_path": audio_path},
                    )
                )
                steps.append(
                    PostProductionStep(
                        id=subtitle_id,
                        system="subtitle",
                        inputs={"cues": [cue.__dict__ for cue in clip.dialogue]},
                        outputs={"subtitle_path": subtitle_path},
                    )
                )
                depends = [tts_id, subtitle_id]

            compose_id = f"{chapter_id}:{clip.shot_id}:compose"
            compose_ids.append(compose_id)
            steps.append(
                PostProductionStep(
                    id=compose_id,
                    system="ffmpeg_compose",
                    inputs={
                        "video_path": clip.video_path,
                        "audio_path": audio_path if clip.dialogue else None,
                        "subtitle_path": subtitle_path if clip.dialogue else None,
                    },
                    outputs={"video_path": f"{work_dir}/{clip.shot_id}.composed.mp4"},
                    depends_on=depends,
                )
            )

        concat_id = f"{chapter_id}:concat"
        concat_list_path = f"{work_dir}/{chapter_id}_concat.txt"
        steps.append(
            PostProductionStep(
                id=concat_id,
                system="ffmpeg_concat",
                inputs={"concat_list": concat_list_path, "clips": [f"{work_dir}/{clip.shot_id}.composed.mp4" for clip in clips]},
                outputs={"video_path": f"{work_dir}/{chapter_id}.mp4"},
                depends_on=compose_ids,
            )
        )
        steps.append(
            PostProductionStep(
                id=f"{chapter_id}:export",
                system="export",
                inputs={"video_path": f"{work_dir}/{chapter_id}.mp4"},
                outputs={"video_path": output_path},
                depends_on=[concat_id],
            )
        )
        return PostProductionPlan(
            project_id=project_id,
            chapter_id=chapter_id,
            steps=steps,
            output_path=output_path,
            metadata={
                "mode": "huobao_style_post_production",
                "clip_count": len(clips),
                "tts_provider": tts_provider,
            },
        )

    def clips_from_shots(
        self,
        shots: list[StudioShot],
        render_results: list[RenderResult],
    ) -> list[PostProductionClip]:
        results = {item.shot_id: item for item in render_results}
        clips: list[PostProductionClip] = []
        for shot in sorted(shots, key=lambda item: item.index):
            result = results.get(shot.id)
            if result is None:
                continue
            duration = float(result.metadata.get("duration") or shot.duration or 0)
            dialogue = [
                cue
                for cue in (
                    self.dialogue_normalizer.parse(shot_id=shot.id, line=line, duration=duration)
                    for line in shot.dialogue
                )
                if cue is not None
            ]
            clips.append(
                PostProductionClip(
                    shot_id=shot.id,
                    video_path=result.output_path,
                    duration=duration,
                    dialogue=dialogue,
                    metadata={"runtime": result.runtime, **dict(result.metadata)},
                )
            )
        return clips


class FFmpegCommandCompiler:
    def compile(self, step: PostProductionStep) -> list[str]:
        if step.system == "ffmpeg_compose":
            command = ["ffmpeg", "-y", "-i", str(step.inputs["video_path"])]
            if step.inputs.get("audio_path"):
                command.extend(["-i", str(step.inputs["audio_path"])])
            subtitle_path = step.inputs.get("subtitle_path")
            if subtitle_path:
                command.extend(["-vf", f"subtitles={subtitle_path}"])
            command.extend(["-shortest", str(step.outputs["video_path"])])
            return command
        if step.system == "ffmpeg_concat":
            return [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(step.inputs["concat_list"]),
                "-c",
                "copy",
                str(step.outputs["video_path"]),
            ]
        raise ValueError(f"Unsupported post-production step: {step.system}")


def _format_ts(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, rem = divmod(millis, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"

