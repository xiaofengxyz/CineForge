from __future__ import annotations

import os
import tempfile

import pytest

from app.services.film.visual_qa import (
    FilmSemanticVisualEvaluator,
    OpenCVVisualEvaluator,
    VisualQAEvaluation,
    merge_visual_qa_evaluations,
)


def _sample_video_bytes() -> bytes:
    """Build a tiny deterministic video that OpenCV can decode in tests."""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    handle = tempfile.NamedTemporaryFile(delete=False, suffix=".avi")
    handle.close()
    try:
        writer = cv2.VideoWriter(
            handle.name,
            cv2.VideoWriter_fourcc(*"MJPG"),
            5.0,
            (64, 64),
        )
        if not writer.isOpened():
            pytest.skip("OpenCV VideoWriter is not available in this environment")
        for index in range(10):
            frame = np.full((64, 64, 3), 72 + index * 8, dtype=np.uint8)
            cv2.rectangle(frame, (8 + index, 16), (36 + index, 48), (220, 220, 220), -1)
            writer.write(frame)
        writer.release()
        with open(handle.name, "rb") as file_obj:
            return file_obj.read()
    finally:
        try:
            os.unlink(handle.name)
        except OSError:
            pass


def _sample_reference_image_bytes() -> bytes:
    """Build a small face-like reference image for deterministic QA tests."""
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    frame = np.full((64, 64, 3), 96, dtype=np.uint8)
    cv2.rectangle(frame, (16, 12), (48, 52), (220, 220, 220), -1)
    ok, payload = cv2.imencode(".png", frame)
    if not ok:
        pytest.skip("OpenCV image encoder is not available in this environment")
    return payload.tobytes()


class _FakeInsightFaceBackend:
    """Tiny identity backend that mimics InsightFace embeddings without native models."""

    def extract_face_embeddings(self, image_bgr: object) -> list[list[float]]:
        """Return one stable normalized embedding for every non-empty image."""
        if image_bgr is None:
            return []
        return [[1.0, 0.0, 0.0]]


class _FakeCLIPBackend:
    """Tiny CLIP backend that returns deterministic frame/text alignment scores."""

    def score_frames(self, *, frames_bgr: list[object], text: str, cv2: object) -> list[float]:
        """Return one semantic score per frame when prompt text exists."""
        return [0.84 for _ in frames_bgr if text.strip()]


def test_opencv_visual_evaluator_returns_supported_film_engine_metrics() -> None:
    """OpenCV QA should emit metrics consumed by the Film Engine QAEngine."""
    evaluation = OpenCVVisualEvaluator(sample_count=5).evaluate_video_bytes(
        video_bytes=_sample_video_bytes(),
        reference_image_bytes=[],
    )

    assert evaluation.status == "succeeded"
    assert set(evaluation.metrics) == {"lighting_similarity", "clip_score"}
    assert 0 <= evaluation.metrics["lighting_similarity"] <= 1
    assert 0 <= evaluation.metrics["clip_score"] <= 1
    assert evaluation.details["frame_count_sampled"] >= 3


def test_semantic_visual_evaluator_returns_face_and_clip_metrics_with_injected_backends() -> None:
    """InsightFace/CLIP QA should map model evidence into Film Engine metrics."""
    evaluation = FilmSemanticVisualEvaluator(
        sample_count=5,
        face_backend=_FakeInsightFaceBackend(),
        clip_backend=_FakeCLIPBackend(),
    ).evaluate_video_bytes(
        video_bytes=_sample_video_bytes(),
        character_reference_image_bytes_by_id={"char-1": [_sample_reference_image_bytes()]},
        prompt_text="young detective stops under a neon sign and looks up",
    )

    assert evaluation.status == "succeeded"
    assert evaluation.evaluator == "insightface_clip"
    assert evaluation.metrics["face_similarity"] == 1.0
    assert evaluation.metrics["clip_score"] == 0.84
    assert evaluation.details["components"]["insightface"]["character_count"] == 1
    assert evaluation.details["components"]["clip"]["frame_score_count"] >= 3


def test_visual_qa_merge_prefers_semantic_clip_over_opencv_proxy() -> None:
    """The combined Film QA payload should let real CLIP override OpenCV proxy scores."""
    merged = merge_visual_qa_evaluations(
        [
            VisualQAEvaluation(metrics={"lighting_similarity": 0.9, "clip_score": 0.55}, evaluator="opencv"),
            VisualQAEvaluation(metrics={"face_similarity": 0.92, "clip_score": 0.81}, evaluator="insightface_clip"),
        ]
    )

    assert merged.evaluator == "film_visual_qa"
    assert merged.status == "succeeded"
    assert merged.metrics == {
        "lighting_similarity": 0.9,
        "clip_score": 0.81,
        "face_similarity": 0.92,
    }
    assert merged.details["metric_sources"]["clip_score"] == "insightface_clip"
