import pytest
from pydantic import BaseModel

from inq_service_svc.services.classifier import (
    classify_inquiry,
    ClassificationResult,
    DEFAULT_CLASSIFICATION,
)


class DummyMessage:
    def __init__(self, parsed):
        self.parsed = parsed


class DummyChoice:
    def __init__(self, message):
        self.message = message


class DummyResponse:
    def __init__(self, parsed):
        # Simulate choices[0].message.parsed shape
        self.choices = [DummyChoice(DummyMessage(parsed))]


class MockClient:
    def __init__(self, to_return=None, to_raise=None):
        self._to_return = to_return
        self._to_raise = to_raise

    def with_options(self, **kwargs):
        return self

    @property
    def beta(self):
        return self

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def parse(self, *args, **kwargs):
        if self._to_raise:
            raise self._to_raise
        return DummyResponse(self._to_return)


def test_successful_classification(monkeypatch):
    parsed = {"category": "Technical", "urgency": "High"}
    mock_client = MockClient(to_return=parsed)
    monkeypatch.setattr(
        "inq_service_svc.services.classifier.get_openai_client", lambda: mock_client
    )
    # run
    res = classify_inquiry("Issue with API", "The API returns 500 when calling /items")
    assert isinstance(res, ClassificationResult)
    assert res.category == "Technical"
    assert res.urgency == "High"


def test_openai_exception_returns_default(monkeypatch):
    mock_client = MockClient(to_raise=RuntimeError("timeout"))
    monkeypatch.setattr(
        "inq_service_svc.services.classifier.get_openai_client", lambda: mock_client
    )
    res = classify_inquiry("Title", "Content")
    assert isinstance(res, ClassificationResult)
    assert res.category == DEFAULT_CLASSIFICATION.category
    assert res.urgency == DEFAULT_CLASSIFICATION.urgency


def test_invalid_response_returns_default(monkeypatch):
    # invalid category / urgency outside allowed lists
    parsed = {"category": "Spam", "urgency": "Critical"}
    mock_client = MockClient(to_return=parsed)
    monkeypatch.setattr(
        "inq_service_svc.services.classifier.get_openai_client", lambda: mock_client
    )
    res = classify_inquiry("Some title", "Some content")
    assert isinstance(res, ClassificationResult)
    assert res.category == DEFAULT_CLASSIFICATION.category
    assert res.urgency == DEFAULT_CLASSIFICATION.urgency
