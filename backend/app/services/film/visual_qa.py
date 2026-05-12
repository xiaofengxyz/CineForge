"""Film Visual QA metrics for generated video tasks."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from statistics import fmean, pstdev
from typing import Any, Mapping, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import storage
from app.models.studio import FileItem


def _clamp01(value: float) -> float:
    """Clamp metric values to the Film Engine QA score range."""
    return max(0.0, min(1.0, float(value)))


def _mean_or_zero(values: Sequence[float]) -> float:
    """Average a metric list while keeping empty evidence deterministic."""
    return fmean(values) if values else 0.0


def _normalize_vector(values: Any) -> list[float]:
    """Convert model embeddings into unit vectors for cosine comparison."""
    try:
        vector = [float(item) for item in values]
    except TypeError:
        return []
    norm = sum(item * item for item in vector) ** 0.5
    if norm <= 0:
        return []
    return [item / norm for item in vector]


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return cosine similarity for already-normalized identity embeddings."""
    if not left or not right or len(left) != len(right):
        return 0.0
    return sum(float(a) * float(b) for a, b in zip(left, right, strict=True))


def _identity_score_from_cosine(cosine: float) -> float:
    """Map InsightFace cosine similarity into the Film Engine 0..1 QA scale."""
    return _clamp01((float(cosine) + 0.20) / 0.80)


def _load_cv_stack() -> tuple[Any | None, Any | None, str | None]:
    """Import OpenCV lazily so app startup can explain missing native wheels."""
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        return None, None, str(exc)
    return cv2, np, None


class InsightFaceEmbeddingBackend:
    """Lazy InsightFace adapter used only when the optional runtime is installed."""

    _app_cache: dict[tuple[str, int, tuple[int, int], tuple[str, ...]], Any] = {}

    def __init__(
        self,
        *,
        model_name: str | None = None,
        ctx_id: int | None = None,
        det_size: tuple[int, int] = (640, 640),
    ) -> None:
        """Configure InsightFace without importing its native dependencies at startup."""
        self.model_name = model_name or os.getenv("CINEFORGE_INSIGHTFACE_MODEL", "buffalo_l")
        self.ctx_id = int(os.getenv("CINEFORGE_INSIGHTFACE_CTX_ID", str(ctx_id if ctx_id is not None else -1)))
        self.det_size = det_size
        providers_text = os.getenv("CINEFORGE_INSIGHTFACE_PROVIDERS", "CPUExecutionProvider")
        self.providers = tuple(item.strip() for item in providers_text.split(",") if item.strip())

    def _app(self) -> Any:
        """Create and cache the InsightFace FaceAnalysis app per process."""
        cache_key = (self.model_name, self.ctx_id, self.det_size, self.providers)
        if cache_key in self._app_cache:
            return self._app_cache[cache_key]
        try:
            from insightface.app import FaceAnalysis  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"insightface_unavailable: {exc}") from exc

        kwargs: dict[str, Any] = {"name": self.model_name}
        if self.providers:
            kwargs["providers"] = list(self.providers)
        app = FaceAnalysis(**kwargs)
        app.prepare(ctx_id=self.ctx_id, det_size=self.det_size)
        self._app_cache[cache_key] = app
        return app

    def extract_face_embeddings(self, image_bgr: Any) -> list[list[float]]:
        """Extract normalized face embeddings from one BGR image."""
        faces = self._app().get(image_bgr)
        if not faces:
            return []

        def face_area(face: Any) -> float:
            bbox = getattr(face, "bbox", None)
            if bbox is None or len(bbox) < 4:
                return 0.0
            return max(0.0, float(bbox[2] - bbox[0])) * max(0.0, float(bbox[3] - bbox[1]))

        embeddings: list[list[float]] = []
        for face in sorted(faces, key=face_area, reverse=True):
            embedding = getattr(face, "normed_embedding", None)
            if embedding is None:
                embedding = getattr(face, "embedding", None)
            normalized = _normalize_vector(embedding)
            if normalized:
                embeddings.append(normalized)
        return embeddings


class TransformersCLIPBackend:
    """Lazy CLIP adapter for image/text alignment checks."""

    _model_cache: dict[tuple[str, str], tuple[Any, Any, Any, Any]] = {}

    def __init__(self, *, model_name: str | None = None, device: str | None = None) -> None:
        """Configure the CLIP checkpoint without loading it until QA runs."""
        self.model_name = model_name or os.getenv("CINEFORGE_CLIP_MODEL", "openai/clip-vit-base-patch32")
        self.device = device or os.getenv("CINEFORGE_CLIP_DEVICE", "cpu")

    def _stack(self) -> tuple[Any, Any, Any, Any]:
        """Load the transformers CLIP stack once per process and device."""
        cache_key = (self.model_name, self.device)
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]
        try:
            import torch  # type: ignore[import-not-found]
            from PIL import Image  # type: ignore[import-not-found]
            from transformers import CLIPModel, CLIPProcessor  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"clip_unavailable: {exc}") from exc

        processor = CLIPProcessor.from_pretrained(self.model_name)
        model = CLIPModel.from_pretrained(self.model_name)
        model.to(self.device)
        model.eval()
        self._model_cache[cache_key] = (torch, Image, processor, model)
        return self._model_cache[cache_key]

    def score_frames(self, *, frames_bgr: list[Any], text: str, cv2: Any) -> list[float]:
        """Return per-frame CLIP image/text alignment scores in 0..1 range."""
        if not frames_bgr or not text.strip():
            return []
        torch, Image, processor, model = self._stack()
        images = [
            Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            for frame in frames_bgr
            if frame is not None
        ]
        if not images:
            return []
        inputs = processor(text=[text], images=images, return_tensors="pt", padding=True)
        inputs = {
            key: value.to(self.device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }
        with torch.no_grad():
            image_features = model.get_image_features(pixel_values=inputs["pixel_values"])
            text_features = model.get_text_features(
                input_ids=inputs["input_ids"],
                attention_mask=inputs.get("attention_mask"),
            )
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            similarities = (image_features @ text_features.T).squeeze(-1).detach().cpu().tolist()
        if isinstance(similarities, float):
            similarities = [similarities]
        return [_clamp01((float(score) + 1.0) / 2.0) for score in similarities]


@dataclass(frozen=True, slots=True)
class VisualQAEvaluation:
    """Structured result produced by an external visual QA evaluator."""

    metrics: dict[str, float] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
    status: str = "succeeded"
    evaluator: str = "opencv"
    reason: str = ""

    def as_result_payload(self) -> dict[str, Any]:
        """Serialize the evaluation for storage in GenerationTask.result."""
        payload = {
            "evaluator": self.evaluator,
            "status": self.status,
            "metrics": dict(self.metrics),
            "details": dict(self.details),
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload


class OpenCVVisualEvaluator:
    """Evaluate generated video readability and continuity with OpenCV."""

    def __init__(self, *, sample_count: int = 12) -> None:
        """Configure how many frames should be sampled from each video."""
        self.sample_count = max(3, int(sample_count))

    def evaluate_video_bytes(
        self,
        *,
        video_bytes: bytes,
        reference_image_bytes: list[bytes] | None = None,
    ) -> VisualQAEvaluation:
        """Evaluate a video from bytes by writing a short-lived temp file."""
        if not video_bytes:
            return VisualQAEvaluation(status="skipped", reason="empty_video_bytes")

        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        try:
            handle.write(video_bytes)
            handle.close()
            return self.evaluate_video_path(
                video_path=handle.name,
                reference_image_bytes=reference_image_bytes or [],
            )
        finally:
            try:
                os.unlink(handle.name)
            except OSError:
                # Temporary-file cleanup must never change the QA result.
                pass

    def evaluate_video_path(
        self,
        *,
        video_path: str,
        reference_image_bytes: list[bytes] | None = None,
    ) -> VisualQAEvaluation:
        """Evaluate a local video path and return Film Engine QA metrics."""
        cv2, np, import_error = _load_cv_stack()
        if cv2 is None or np is None:
            return VisualQAEvaluation(
                status="skipped",
                reason=f"opencv_unavailable: {import_error or 'unknown error'}",
            )

        frames = self._sample_frames(cv2=cv2, video_path=video_path)
        if not frames:
            return VisualQAEvaluation(status="skipped", reason="no_decodable_frames")

        luma_values = [self._luma_mean(cv2=cv2, frame=frame) for frame in frames]
        sharpness_values = [self._sharpness_score(cv2=cv2, frame=frame) for frame in frames]
        motion_values = self._frame_delta_scores(cv2=cv2, frames=frames)
        reference_luma_values = self._reference_luma_values(
            cv2=cv2,
            np=np,
            reference_image_bytes=reference_image_bytes or [],
        )

        luma_mean = fmean(luma_values)
        luma_std = pstdev(luma_values) if len(luma_values) > 1 else 0.0
        lighting_stability = 1.0 - min(luma_std / 0.30, 1.0)
        exposure_score = 1.0 - min(abs(luma_mean - 0.45) / 0.45, 1.0)
        lighting_similarity = (0.65 * lighting_stability) + (0.35 * exposure_score)

        if reference_luma_values:
            reference_luma = fmean(reference_luma_values)
            reference_match = 1.0 - min(abs(luma_mean - reference_luma) / 0.50, 1.0)
            # Reference frames are stronger evidence than a generic exposure prior.
            lighting_similarity = (0.55 * lighting_similarity) + (0.45 * reference_match)

        motion_score = fmean(motion_values) if motion_values else 0.72
        sharpness_score = fmean(sharpness_values)
        non_blank_score = 1.0 - min(abs(luma_mean - 0.05) / 0.05, 1.0) if luma_mean < 0.05 else 1.0
        clip_score = (0.45 * sharpness_score) + (0.35 * motion_score) + (0.20 * non_blank_score)

        metrics = {
            "lighting_similarity": round(_clamp01(lighting_similarity), 4),
            "clip_score": round(_clamp01(clip_score), 4),
        }
        details = {
            "frame_count_sampled": len(frames),
            "reference_count": len(reference_luma_values),
            "luma_mean": round(luma_mean, 4),
            "luma_std": round(luma_std, 4),
            "sharpness_mean": round(sharpness_score, 4),
            "motion_mean": round(motion_score, 4),
            "metric_mapping": {
                "lighting_similarity": "OpenCV luma stability plus optional reference-frame luma match",
                "clip_score": "OpenCV visual readability proxy from sharpness, motion, and non-blank frames",
            },
        }
        return VisualQAEvaluation(metrics=metrics, details=details)

    def _sample_frames(self, *, cv2: Any, video_path: str) -> list[Any]:
        """Sample frames evenly from the video without loading the full file."""
        capture = cv2.VideoCapture(video_path)
        try:
            if not capture.isOpened():
                return []

            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if frame_count > 0:
                max_index = max(frame_count - 1, 0)
                positions = {
                    int(round(index * max_index / max(self.sample_count - 1, 1)))
                    for index in range(self.sample_count)
                }
                frames = []
                for position in sorted(positions):
                    capture.set(cv2.CAP_PROP_POS_FRAMES, position)
                    ok, frame = capture.read()
                    if ok and frame is not None:
                        frames.append(frame)
                return frames

            frames = []
            while len(frames) < self.sample_count:
                ok, frame = capture.read()
                if not ok or frame is None:
                    break
                frames.append(frame)
            return frames
        finally:
            capture.release()

    def _luma_mean(self, *, cv2: Any, frame: Any) -> float:
        """Calculate normalized frame luminance for lighting checks."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return _clamp01(float(gray.mean()) / 255.0)

    def _sharpness_score(self, *, cv2: Any, frame: Any) -> float:
        """Estimate sharpness from Laplacian variance and normalize it."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        return _clamp01(variance / 500.0)

    def _frame_delta_scores(self, *, cv2: Any, frames: list[Any]) -> list[float]:
        """Estimate whether frame-to-frame motion is stable rather than blank or flickery."""
        if len(frames) < 2:
            return []

        scores: list[float] = []
        previous = None
        for frame in frames:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (64, 64))
            if previous is not None:
                delta = float(cv2.absdiff(previous, resized).mean()) / 255.0
                scores.append(1.0 - min(abs(delta - 0.08) / 0.30, 1.0))
            previous = resized
        return [_clamp01(score) for score in scores]

    def _reference_luma_values(
        self,
        *,
        cv2: Any,
        np: Any,
        reference_image_bytes: list[bytes],
    ) -> list[float]:
        """Decode reference images and return normalized luminance samples."""
        values: list[float] = []
        for payload in reference_image_bytes:
            if not payload:
                continue
            image_array = np.frombuffer(payload, dtype=np.uint8)
            image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
            if image is None:
                continue
            values.append(self._luma_mean(cv2=cv2, frame=image))
        return values


class FilmSemanticVisualEvaluator:
    """Evaluate identity consistency and prompt alignment with optional AI models."""

    def __init__(
        self,
        *,
        sample_count: int = 8,
        face_backend: Any | None = None,
        clip_backend: Any | None = None,
    ) -> None:
        """Allow tests and deployments to inject model backends without hard coupling."""
        self.sample_count = max(3, int(sample_count))
        self.face_backend = face_backend
        self.clip_backend = clip_backend

    def evaluate_video_bytes(
        self,
        *,
        video_bytes: bytes,
        character_reference_image_bytes_by_id: Mapping[str, list[bytes]] | None = None,
        prompt_text: str | None = None,
    ) -> VisualQAEvaluation:
        """Evaluate advanced Film QA evidence from video bytes."""
        if not video_bytes:
            return VisualQAEvaluation(
                status="skipped",
                evaluator="insightface_clip",
                reason="empty_video_bytes",
            )

        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        try:
            handle.write(video_bytes)
            handle.close()
            return self.evaluate_video_path(
                video_path=handle.name,
                character_reference_image_bytes_by_id=character_reference_image_bytes_by_id or {},
                prompt_text=prompt_text,
            )
        finally:
            try:
                os.unlink(handle.name)
            except OSError:
                # Temporary-file cleanup is not part of QA semantics.
                pass

    def evaluate_video_path(
        self,
        *,
        video_path: str,
        character_reference_image_bytes_by_id: Mapping[str, list[bytes]] | None = None,
        prompt_text: str | None = None,
    ) -> VisualQAEvaluation:
        """Run InsightFace and CLIP checks when their optional stacks are available."""
        cv2, np, import_error = _load_cv_stack()
        if cv2 is None or np is None:
            return VisualQAEvaluation(
                status="skipped",
                evaluator="insightface_clip",
                reason=f"opencv_unavailable: {import_error or 'unknown error'}",
            )

        frames = OpenCVVisualEvaluator(sample_count=self.sample_count)._sample_frames(
            cv2=cv2,
            video_path=video_path,
        )
        if not frames:
            return VisualQAEvaluation(
                status="skipped",
                evaluator="insightface_clip",
                reason="no_decodable_frames",
            )

        character_refs = character_reference_image_bytes_by_id or {}
        metrics: dict[str, float] = {}
        details: dict[str, Any] = {"frame_count_sampled": len(frames), "components": {}}

        face_metrics, face_details = self._evaluate_face_consistency(
            cv2=cv2,
            np=np,
            frames=frames,
            character_reference_image_bytes_by_id=character_refs,
        )
        metrics.update(face_metrics)
        details["components"]["insightface"] = face_details

        clip_metrics, clip_details = self._evaluate_clip_alignment(
            cv2=cv2,
            frames=frames,
            prompt_text=prompt_text or "",
        )
        metrics.update(clip_metrics)
        details["components"]["clip"] = clip_details

        if metrics:
            return VisualQAEvaluation(
                metrics=metrics,
                details=details,
                evaluator="insightface_clip",
            )

        reasons = [
            str(component.get("reason"))
            for component in details["components"].values()
            if isinstance(component, dict) and component.get("reason")
        ]
        return VisualQAEvaluation(
            status="skipped",
            details=details,
            evaluator="insightface_clip",
            reason="; ".join(reasons) or "no_advanced_qa_metrics",
        )

    def _decode_image(self, *, cv2: Any, np: Any, payload: bytes) -> Any | None:
        """Decode one reference image payload into OpenCV BGR format."""
        if not payload:
            return None
        image_array = np.frombuffer(payload, dtype=np.uint8)
        return cv2.imdecode(image_array, cv2.IMREAD_COLOR)

    def _evaluate_face_consistency(
        self,
        *,
        cv2: Any,
        np: Any,
        frames: list[Any],
        character_reference_image_bytes_by_id: Mapping[str, list[bytes]],
    ) -> tuple[dict[str, float], dict[str, Any]]:
        """Use InsightFace embeddings to compare generated faces with character refs."""
        if not character_reference_image_bytes_by_id:
            return {}, {"status": "skipped", "reason": "no_character_references"}

        backend = self.face_backend or InsightFaceEmbeddingBackend()
        reference_embeddings: dict[str, list[list[float]]] = {}
        decode_errors: list[str] = []
        try:
            for character_id, payloads in character_reference_image_bytes_by_id.items():
                for payload in payloads:
                    image = self._decode_image(cv2=cv2, np=np, payload=payload)
                    if image is None:
                        decode_errors.append(f"{character_id}:decode_failed")
                        continue
                    reference_embeddings.setdefault(character_id, []).extend(
                        backend.extract_face_embeddings(image)
                    )
        except Exception as exc:  # noqa: BLE001
            return {}, {"status": "skipped", "reason": str(exc), "decode_errors": decode_errors}

        reference_embeddings = {
            character_id: embeddings
            for character_id, embeddings in reference_embeddings.items()
            if embeddings
        }
        if not reference_embeddings:
            return {
                "face_similarity": 0.0,
            }, {
                "status": "succeeded",
                "reason": "no_reference_faces_detected",
                "character_count": len(character_reference_image_bytes_by_id),
                "decode_errors": decode_errors,
            }

        generated_embeddings: list[list[float]] = []
        try:
            for frame in frames:
                generated_embeddings.extend(backend.extract_face_embeddings(frame))
        except Exception as exc:  # noqa: BLE001
            return {}, {"status": "skipped", "reason": str(exc), "decode_errors": decode_errors}

        if not generated_embeddings:
            return {
                "face_similarity": 0.0,
            }, {
                "status": "succeeded",
                "reason": "no_generated_faces_detected",
                "character_count": len(reference_embeddings),
                "decode_errors": decode_errors,
            }

        per_character: dict[str, dict[str, float]] = {}
        character_scores: list[float] = []
        for character_id, ref_vectors in reference_embeddings.items():
            best_cosine = max(
                _cosine_similarity(ref_vector, generated_vector)
                for ref_vector in ref_vectors
                for generated_vector in generated_embeddings
            )
            score = _identity_score_from_cosine(best_cosine)
            character_scores.append(score)
            per_character[character_id] = {
                "best_cosine": round(best_cosine, 4),
                "score": round(score, 4),
                "reference_face_count": float(len(ref_vectors)),
            }

        face_similarity = round(_clamp01(_mean_or_zero(character_scores)), 4)
        return {
            "face_similarity": face_similarity,
        }, {
            "status": "succeeded",
            "character_count": len(reference_embeddings),
            "generated_face_count": len(generated_embeddings),
            "per_character": per_character,
            "decode_errors": decode_errors,
            "metric_mapping": "InsightFace identity embedding cosine mapped into face_similarity",
        }

    def _evaluate_clip_alignment(
        self,
        *,
        cv2: Any,
        frames: list[Any],
        prompt_text: str,
    ) -> tuple[dict[str, float], dict[str, Any]]:
        """Use CLIP to compare sampled frames with the compiled story/prompt text."""
        prompt = prompt_text.strip()
        if not prompt:
            return {}, {"status": "skipped", "reason": "empty_prompt_text"}

        backend = self.clip_backend or TransformersCLIPBackend()
        try:
            scores = backend.score_frames(frames_bgr=frames, text=prompt, cv2=cv2)
        except Exception as exc:  # noqa: BLE001
            return {}, {"status": "skipped", "reason": str(exc)}
        if not scores:
            return {}, {"status": "skipped", "reason": "no_clip_scores"}

        sorted_scores = sorted((_clamp01(score) for score in scores), reverse=True)
        top_count = max(1, len(sorted_scores) // 2)
        # Video prompts often describe the key action, so top-frame evidence is less brittle.
        clip_score = round(_clamp01(fmean(sorted_scores[:top_count])), 4)
        return {
            "clip_score": clip_score,
        }, {
            "status": "succeeded",
            "frame_score_count": len(scores),
            "top_frame_count": top_count,
            "mean_score": round(_mean_or_zero(scores), 4),
            "best_score": round(max(scores), 4),
            "prompt_excerpt": prompt[:240],
            "metric_mapping": "CLIP image/text cosine mapped into semantic clip_score",
        }


def merge_visual_qa_evaluations(
    evaluations: Sequence[VisualQAEvaluation],
    *,
    evaluator: str = "film_visual_qa",
) -> VisualQAEvaluation:
    """Merge multiple evaluator payloads while letting stronger evidence override proxies."""
    metrics: dict[str, float] = {}
    metric_sources: dict[str, str] = {}
    components: list[dict[str, Any]] = []
    reasons: list[str] = []
    for evaluation in evaluations:
        components.append(evaluation.as_result_payload())
        if evaluation.reason:
            reasons.append(f"{evaluation.evaluator}:{evaluation.reason}")
        for metric, score in evaluation.metrics.items():
            metrics[metric] = score
            metric_sources[metric] = evaluation.evaluator

    status = "succeeded" if metrics else "skipped"
    details = {
        "components": components,
        "metric_sources": metric_sources,
    }
    return VisualQAEvaluation(
        metrics=metrics,
        details=details,
        status=status,
        evaluator=evaluator,
        reason="; ".join(reasons) if status == "skipped" else "",
    )


async def _download_file_bytes(file_obj: FileItem) -> bytes:
    """Download a FileItem from configured object storage."""
    if not file_obj.storage_key:
        raise RuntimeError(f"FileItem has no storage_key: {file_obj.id}")
    return await storage.download_file(key=file_obj.storage_key)


async def _download_reference_bytes(
    db: AsyncSession,
    *,
    file_ids: Sequence[str],
) -> tuple[list[bytes], list[str]]:
    """Download optional reference files and keep all failures explainable."""
    payloads: list[bytes] = []
    errors: list[str] = []
    for file_id in file_ids:
        file_obj = await db.get(FileItem, file_id)
        if file_obj is None:
            errors.append(f"missing_reference:{file_id}")
            continue
        try:
            payloads.append(await _download_file_bytes(file_obj))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"reference_download_failed:{file_id}:{exc}")
    return payloads, errors


async def _download_character_reference_bytes(
    db: AsyncSession,
    *,
    character_reference_file_ids_by_id: Mapping[str, Sequence[str]],
) -> tuple[dict[str, list[bytes]], list[str]]:
    """Download character reference images grouped by character id."""
    result: dict[str, list[bytes]] = {}
    errors: list[str] = []
    for character_id, file_ids in character_reference_file_ids_by_id.items():
        payloads, ref_errors = await _download_reference_bytes(db, file_ids=list(file_ids))
        if payloads:
            result[character_id] = payloads
        errors.extend(f"{character_id}:{item}" for item in ref_errors)
    return result, errors


async def evaluate_file_item_with_opencv(
    db: AsyncSession,
    *,
    video_file: FileItem,
    reference_file_ids: list[str] | None = None,
) -> VisualQAEvaluation:
    """Run OpenCV QA for a stored generated video and optional reference frames."""
    try:
        video_bytes = await _download_file_bytes(video_file)
    except Exception as exc:  # noqa: BLE001
        return VisualQAEvaluation(status="skipped", reason=f"video_download_failed: {exc}")

    reference_bytes, reference_errors = await _download_reference_bytes(
        db,
        file_ids=reference_file_ids or [],
    )

    evaluation = OpenCVVisualEvaluator().evaluate_video_bytes(
        video_bytes=video_bytes,
        reference_image_bytes=reference_bytes,
    )
    if not reference_errors:
        return evaluation
    details = {**evaluation.details, "reference_errors": reference_errors}
    return VisualQAEvaluation(
        metrics=evaluation.metrics,
        details=details,
        status=evaluation.status,
        evaluator=evaluation.evaluator,
        reason=evaluation.reason,
    )


async def evaluate_file_item_with_film_visual_qa(
    db: AsyncSession,
    *,
    video_file: FileItem,
    reference_file_ids: list[str] | None = None,
    character_reference_file_ids_by_id: Mapping[str, Sequence[str]] | None = None,
    prompt_text: str | None = None,
) -> VisualQAEvaluation:
    """Run the full Film QA chain: OpenCV baseline plus optional InsightFace/CLIP."""
    try:
        video_bytes = await _download_file_bytes(video_file)
    except Exception as exc:  # noqa: BLE001
        return VisualQAEvaluation(
            status="skipped",
            evaluator="film_visual_qa",
            reason=f"video_download_failed: {exc}",
        )

    reference_bytes, reference_errors = await _download_reference_bytes(
        db,
        file_ids=reference_file_ids or [],
    )
    character_reference_bytes_by_id, character_reference_errors = await _download_character_reference_bytes(
        db,
        character_reference_file_ids_by_id=character_reference_file_ids_by_id or {},
    )

    opencv_evaluation = OpenCVVisualEvaluator().evaluate_video_bytes(
        video_bytes=video_bytes,
        reference_image_bytes=reference_bytes,
    )
    semantic_evaluation = FilmSemanticVisualEvaluator().evaluate_video_bytes(
        video_bytes=video_bytes,
        character_reference_image_bytes_by_id=character_reference_bytes_by_id,
        prompt_text=prompt_text,
    )
    evaluation = merge_visual_qa_evaluations([opencv_evaluation, semantic_evaluation])
    all_errors = [*reference_errors, *character_reference_errors]
    if not all_errors:
        return evaluation
    details = {**evaluation.details, "reference_errors": all_errors}
    return VisualQAEvaluation(
        metrics=evaluation.metrics,
        details=details,
        status=evaluation.status,
        evaluator=evaluation.evaluator,
        reason=evaluation.reason,
    )
