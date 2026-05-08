from src.film_engine import (
    FFmpegCommandCompiler,
    PostProductionClip,
    PostProductionPlanner,
    RenderResult,
    StudioShot,
    SubtitleCompiler,
)


def test_builds_huobao_style_post_production_plan():
    planner = PostProductionPlanner()
    clips = [
        PostProductionClip(
            shot_id="shot_001",
            video_path="renders/shot_001.mp4",
            duration=5,
            dialogue=[
                planner.dialogue_normalizer.parse(
                    shot_id="shot_001",
                    line="Ari: Keep walking.",
                    duration=5,
                )
            ],
        ),
        PostProductionClip(
            shot_id="shot_002",
            video_path="renders/shot_002.mp4",
            duration=4,
        ),
    ]
    clips[0].dialogue = [cue for cue in clips[0].dialogue if cue]

    plan = planner.plan_chapter(
        project_id="project_001",
        chapter_id="chapter_001",
        clips=clips,
        output_path="exports/chapter_001.mp4",
        work_dir="output/post/chapter_001",
        tts_provider="minimax",
    )

    assert plan.metadata["mode"] == "huobao_style_post_production"
    assert [step.system for step in plan.steps] == [
        "tts",
        "subtitle",
        "ffmpeg_compose",
        "ffmpeg_compose",
        "ffmpeg_concat",
        "export",
    ]
    first_compose = plan.steps_by_system("ffmpeg_compose")[0]
    assert first_compose.depends_on == [
        "chapter_001:shot_001:tts",
        "chapter_001:shot_001:subtitle",
    ]
    assert first_compose.inputs["audio_path"] == "output/post/chapter_001/shot_001.mp3"
    assert first_compose.inputs["subtitle_path"] == "output/post/chapter_001/shot_001.srt"
    concat = plan.steps_by_system("ffmpeg_concat")[0]
    assert concat.depends_on == [
        "chapter_001:shot_001:compose",
        "chapter_001:shot_002:compose",
    ]
    assert plan.steps[-1].outputs["video_path"] == "exports/chapter_001.mp4"


def test_compiles_subtitles_and_ffmpeg_argument_vectors():
    compiler = SubtitleCompiler()
    command_compiler = FFmpegCommandCompiler()
    clip = PostProductionClip(
        shot_id="shot_001",
        video_path="renders/shot_001.mp4",
        duration=3,
        dialogue=[
            PostProductionPlanner().dialogue_normalizer.parse(
                shot_id="shot_001",
                line="Ari: We only get one try.",
                duration=3,
            )
        ],
    )
    clip.dialogue = [cue for cue in clip.dialogue if cue]

    srt = compiler.to_srt(compiler.cues_for_clip(clip))

    assert "00:00:00,500 --> 00:00:02,500" in srt
    assert "We only get one try." in srt

    plan = PostProductionPlanner().plan_chapter(
        project_id="project_001",
        chapter_id="chapter_001",
        clips=[clip],
        output_path="exports/chapter_001.mp4",
    )
    compose_command = command_compiler.compile(plan.steps_by_system("ffmpeg_compose")[0])
    concat_command = command_compiler.compile(plan.steps_by_system("ffmpeg_concat")[0])

    assert compose_command[:4] == ["ffmpeg", "-y", "-i", "renders/shot_001.mp4"]
    assert "-vf" in compose_command
    assert "-shortest" in compose_command
    assert concat_command[:6] == ["ffmpeg", "-y", "-f", "concat", "-safe", "0"]


def test_derives_post_production_clips_from_studio_shots_and_render_results():
    planner = PostProductionPlanner()
    shots = [
        StudioShot(
            id="shot_002",
            project_id="project_001",
            chapter_id="chapter_001",
            index=2,
            duration=4,
            dialogue=["ambient: bgm"],
        ),
        StudioShot(
            id="shot_001",
            project_id="project_001",
            chapter_id="chapter_001",
            index=1,
            duration=5,
            dialogue=["Ari: Hold the frame."],
        ),
    ]
    render_results = [
        RenderResult(
            shot_id="shot_001",
            output_path="renders/shot_001.mp4",
            runtime="kling",
            metadata={"duration": 5},
        ),
        RenderResult(
            shot_id="shot_002",
            output_path="renders/shot_002.mp4",
            runtime="vidu",
        ),
    ]

    clips = planner.clips_from_shots(shots, render_results)

    assert [clip.shot_id for clip in clips] == ["shot_001", "shot_002"]
    assert clips[0].dialogue[0].speaker_name == "Ari"
    assert clips[0].dialogue[0].text == "Hold the frame."
    assert clips[1].dialogue == []
    assert clips[1].metadata["runtime"] == "vidu"
