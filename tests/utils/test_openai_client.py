import logging
import pytest

import inq_service_svc.utils.openai_client as openai_client
from inq_service_svc import config


def test_initializes_openai_client_with_api_key(monkeypatch):
    # Ensure no leaked singleton
    monkeypatch.setattr(openai_client, "_client", None)

    called = {}

    class MockOpenAI:
        def __init__(self, api_key):
            called['api_key'] = api_key

    # Patch the OpenAI constructor used in the module
    monkeypatch.setattr(openai_client, "OpenAI", MockOpenAI)
    # Ensure config has expected API key
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")

    client = openai_client.get_openai_client()
    assert isinstance(client, MockOpenAI)
    assert called.get('api_key') == "test-key"


def test_returns_cached_singleton(monkeypatch):
    monkeypatch.setattr(openai_client, "_client", None)

    calls = {"count": 0}
    instance = object()

    def mock_ctor(api_key):
        calls['count'] += 1
        return instance

    monkeypatch.setattr(openai_client, "OpenAI", mock_ctor)
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-key")

    c1 = openai_client.get_openai_client()
    c2 = openai_client.get_openai_client()

    assert c1 is c2
    assert calls['count'] == 1


def test_missing_api_key_raises_and_logs(monkeypatch, caplog):
    monkeypatch.setattr(openai_client, "_client", None)
    monkeypatch.setattr(config, "OPENAI_API_KEY", None)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError):
            openai_client.get_openai_client()

    assert any("OPENAI_API_KEY" in rec.getMessage() for rec in caplog.records), "Expected log mentioning OPENAI_API_KEY"
