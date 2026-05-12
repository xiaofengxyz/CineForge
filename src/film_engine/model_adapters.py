from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Protocol


SECRET_KEYS = ("api_key", "authorization", "x-api-key")


def _clean_text(value: Any) -> str:
    """Normalize optional configuration text without leaking sentinel values."""
    return str(value or "").strip()


def _redact_headers(headers: dict[str, str]) -> dict[str, str]:
    """Return headers safe for logs, progress indexes, and API responses."""
    safe: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in SECRET_KEYS:
            safe[key] = "***configured***" if value else ""
        else:
            safe[key] = value
    return safe


@dataclass(frozen=True)
class ModelEndpointConfig:
    """Runtime endpoint config for one model family.

    Film Core receives provider-neutral work items. This object is the boundary
    where a concrete provider/model/base_url/api_key is bound before execution.
    """

    provider: str
    model: str
    base_url: str = ""
    api_key: str = ""
    timeout_seconds: float = 60.0
    headers: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "ModelEndpointConfig":
        """Create config from API/JSON input and accept baseurl/base_url aliases."""
        return cls(
            provider=_clean_text(value.get("provider") or value.get("runtime_provider") or "deterministic"),
            model=_clean_text(value.get("model") or value.get("runtime_model") or "deterministic"),
            base_url=_clean_text(value.get("base_url") or value.get("baseurl")),
            api_key=_clean_text(value.get("api_key") or value.get("apikey")),
            timeout_seconds=float(value.get("timeout_seconds") or 60.0),
            headers=dict(value.get("headers") or {}),
            metadata=dict(value.get("metadata") or {}),
        )

    def safe_dict(self) -> dict[str, Any]:
        """Serialize endpoint metadata without exposing raw credentials."""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key_configured": bool(self.api_key),
            "timeout_seconds": self.timeout_seconds,
            "headers": _redact_headers(dict(self.headers)),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeModelProfiles:
    """Model endpoint set used by the text-to-drama operating workflow."""

    text: ModelEndpointConfig = field(
        default_factory=lambda: ModelEndpointConfig(provider="deterministic", model="novel-planner")
    )
    image: ModelEndpointConfig = field(
        default_factory=lambda: ModelEndpointConfig(provider="deterministic", model="storyboard-image")
    )
    video: ModelEndpointConfig = field(
        default_factory=lambda: ModelEndpointConfig(provider="deterministic", model="storyboard-video")
    )

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "RuntimeModelProfiles":
        """Load text/image/video endpoint config from a loose API payload."""
        payload = value or {}
        return cls(
            text=ModelEndpointConfig.from_mapping(dict(payload.get("text") or {})),
            image=ModelEndpointConfig.from_mapping(dict(payload.get("image") or {})),
            video=ModelEndpointConfig.from_mapping(dict(payload.get("video") or {})),
        )

    def safe_dict(self) -> dict[str, Any]:
        """Return model profiles suitable for persisted run state."""
        return {
            "text": self.text.safe_dict(),
            "image": self.image.safe_dict(),
            "video": self.video.safe_dict(),
        }


@dataclass(frozen=True)
class ModelInvocation:
    """Provider-neutral model call request emitted by workflow stages."""

    stage_id: str
    modality: str
    prompt: str
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Serialize the invocation without endpoint credentials."""
        return {
            "stage_id": self.stage_id,
            "modality": self.modality,
            "prompt": self.prompt,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class PreparedModelCall:
    """Inspectable model call plan with credentials removed from safe output."""

    endpoint: ModelEndpointConfig
    invocation: ModelInvocation
    request: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)

    def safe_dict(self) -> dict[str, Any]:
        """Return a debuggable model call without exposing api_key."""
        return {
            "endpoint": self.endpoint.safe_dict(),
            "invocation": self.invocation.as_dict(),
            "request": dict(self.request),
            "headers": _redact_headers(dict(self.headers)),
        }


@dataclass(frozen=True)
class ModelInvocationResult:
    """Normalized result returned by all runtime model adapters."""

    status: str
    content: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Serialize result for persisted workflow state."""
        payload = {"status": self.status, "content": self.content, "raw": dict(self.raw)}
        if self.error:
            payload["error"] = self.error
        return payload


class ModelAdapter(Protocol):
    """Adapter contract implemented by deterministic and HTTP runtimes."""

    def prepare(
        self,
        *,
        endpoint: ModelEndpointConfig,
        invocation: ModelInvocation,
    ) -> PreparedModelCall:
        """Build a provider-specific request plan."""

    def invoke(
        self,
        *,
        endpoint: ModelEndpointConfig,
        invocation: ModelInvocation,
    ) -> ModelInvocationResult:
        """Execute the provider-specific request."""


class DeterministicModelAdapter:
    """Local fallback adapter used for tests, demos, and offline planning."""

    def prepare(
        self,
        *,
        endpoint: ModelEndpointConfig,
        invocation: ModelInvocation,
    ) -> PreparedModelCall:
        request = {
            "model": endpoint.model,
            "modality": invocation.modality,
            "prompt": invocation.prompt,
            "payload": dict(invocation.payload),
        }
        return PreparedModelCall(endpoint=endpoint, invocation=invocation, request=request)

    def invoke(
        self,
        *,
        endpoint: ModelEndpointConfig,
        invocation: ModelInvocation,
    ) -> ModelInvocationResult:
        prepared = self.prepare(endpoint=endpoint, invocation=invocation)
        content = json.dumps(prepared.request, ensure_ascii=False, sort_keys=True)
        return ModelInvocationResult(status="succeeded", content=content, raw=prepared.safe_dict())


class OpenAICompatibleTextAdapter:
    """Minimal OpenAI-compatible chat adapter for flexible base_url/api_key use."""

    def _chat_url(self, base_url: str) -> str:
        base = base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def prepare(
        self,
        *,
        endpoint: ModelEndpointConfig,
        invocation: ModelInvocation,
    ) -> PreparedModelCall:
        headers = {
            "Content-Type": "application/json",
            **dict(endpoint.headers),
        }
        if endpoint.api_key:
            headers["Authorization"] = f"Bearer {endpoint.api_key}"
        request = {
            "model": endpoint.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are CineForge's isolated model runtime adapter.",
                },
                {"role": "user", "content": invocation.prompt},
            ],
            **dict(invocation.payload),
        }
        return PreparedModelCall(endpoint=endpoint, invocation=invocation, request=request, headers=headers)

    def invoke(
        self,
        *,
        endpoint: ModelEndpointConfig,
        invocation: ModelInvocation,
    ) -> ModelInvocationResult:
        if not endpoint.base_url:
            return ModelInvocationResult(status="failed", error="base_url is required for HTTP invocation")

        prepared = self.prepare(endpoint=endpoint, invocation=invocation)
        data = json.dumps(prepared.request).encode("utf-8")
        request = urllib.request.Request(
            self._chat_url(endpoint.base_url),
            data=data,
            headers=prepared.headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=endpoint.timeout_seconds) as response:
                raw_text = response.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError) as exc:
            return ModelInvocationResult(status="failed", error=str(exc), raw=prepared.safe_dict())

        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError:
            return ModelInvocationResult(status="succeeded", content=raw_text, raw=prepared.safe_dict())

        choices = raw.get("choices") if isinstance(raw, dict) else None
        content = ""
        if choices and isinstance(choices, list):
            message = choices[0].get("message") if isinstance(choices[0], dict) else None
            if isinstance(message, dict):
                content = str(message.get("content") or "")
        return ModelInvocationResult(status="succeeded", content=content, raw=raw)


class RuntimeAdapterLayer:
    """Registry that keeps model runtime selection outside Film Core."""

    def __init__(self, adapters: dict[str, ModelAdapter] | None = None) -> None:
        self.adapters: dict[str, ModelAdapter] = {
            "deterministic": DeterministicModelAdapter(),
            "openai": OpenAICompatibleTextAdapter(),
            "openai_compatible": OpenAICompatibleTextAdapter(),
        }
        self.adapters.update(adapters or {})

    def adapter_for(self, endpoint: ModelEndpointConfig) -> ModelAdapter:
        """Resolve an adapter without coupling callers to provider SDKs."""
        provider = endpoint.provider.strip().lower() or "deterministic"
        if provider in self.adapters:
            return self.adapters[provider]
        if endpoint.base_url:
            return self.adapters["openai_compatible"]
        return self.adapters["deterministic"]

    def prepare(
        self,
        *,
        endpoint: ModelEndpointConfig,
        invocation: ModelInvocation,
    ) -> PreparedModelCall:
        """Prepare a call for audit or deferred execution."""
        return self.adapter_for(endpoint).prepare(endpoint=endpoint, invocation=invocation)

    def invoke(
        self,
        *,
        endpoint: ModelEndpointConfig,
        invocation: ModelInvocation,
    ) -> ModelInvocationResult:
        """Execute a call through the resolved adapter."""
        return self.adapter_for(endpoint).invoke(endpoint=endpoint, invocation=invocation)

