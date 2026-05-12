import json

from src.film_engine import ModelEndpointConfig, ModelInvocation, RuntimeAdapterLayer


def test_model_endpoint_config_accepts_baseurl_alias_and_redacts_api_key():
    config = ModelEndpointConfig.from_mapping(
        {
            "provider": "openai",
            "model": "gpt-runtime",
            "baseurl": "https://runtime.example",
            "api_key": "secret-token",
            "headers": {"x-api-key": "secret-token", "X-Trace": "trace-1"},
        }
    )

    safe = config.safe_dict()

    assert config.base_url == "https://runtime.example"
    assert config.api_key == "secret-token"
    assert safe["api_key_configured"] is True
    assert safe["headers"]["x-api-key"] == "***configured***"
    assert "secret-token" not in json.dumps(safe)


def test_runtime_adapter_layer_prepares_provider_call_without_leaking_credentials():
    config = ModelEndpointConfig(
        provider="openai",
        model="gpt-runtime",
        base_url="https://runtime.example/v1",
        api_key="secret-token",
    )
    invocation = ModelInvocation(
        stage_id="novel_engine",
        modality="text",
        prompt="Generate a continuity-safe novel plan.",
        payload={"temperature": 0.2},
    )

    prepared = RuntimeAdapterLayer().prepare(endpoint=config, invocation=invocation)
    safe = prepared.safe_dict()

    assert prepared.headers["Authorization"] == "Bearer secret-token"
    assert safe["headers"]["Authorization"] == "***configured***"
    assert safe["request"]["model"] == "gpt-runtime"
    assert safe["invocation"]["stage_id"] == "novel_engine"
    assert "secret-token" not in json.dumps(safe)

