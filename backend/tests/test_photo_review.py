"""Claude photo reviewer, tested with a fake client (no network, no API key)."""

import base64
from types import SimpleNamespace

import anthropic
import httpx2  # the HTTP library the anthropic SDK is built on
import pytest

from app.photo_review import (
    MAX_IMAGE_BYTES,
    MODEL,
    PhotoAssessment,
    detect_media_type,
    make_claude_reviewer,
)
from app.reports import PhotoVerdict

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32
GIF = b"GIF89a" + b"\x00" * 32

REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def assessment(**overrides) -> PhotoAssessment:
    fields = {
        "is_sidewalk_hazard": True,
        "kind": "snow",
        "severity": "severe",
        "blocked": True,
        "confidence": "high",
        "accessibility_issue": True,
        "description": "Snowbank covers the whole sidewalk.",
    }
    return PhotoAssessment(**(fields | overrides))


class FakeMessages:
    def __init__(self, result):
        self._result = result
        self.calls: list[dict] = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._result, BaseException):
            raise self._result
        return self._result


class FakeClient:
    """Stands in for anthropic.Anthropic: with_options() and messages.parse()."""

    def __init__(self, result):
        self.messages = FakeMessages(result)
        self.options: dict = {}

    def with_options(self, **kwargs):
        self.options = kwargs
        return self


def answering(parsed: PhotoAssessment | None, stop_reason: str = "end_turn") -> FakeClient:
    return FakeClient(SimpleNamespace(stop_reason=stop_reason, parsed_output=parsed))


def review(client: FakeClient, photo: bytes = JPEG) -> PhotoVerdict:
    return make_claude_reviewer(client)(photo)


# --- Verdicts -------------------------------------------------------------


def test_blocked_hazard_with_high_confidence_is_confirmed():
    assert review(answering(assessment())) is PhotoVerdict.CONFIRMED


def test_blocked_hazard_with_medium_confidence_is_confirmed():
    assert review(answering(assessment(confidence="medium"))) is PhotoVerdict.CONFIRMED


def test_photo_that_is_not_a_sidewalk_hazard_is_rejected():
    parsed = assessment(is_sidewalk_hazard=False, kind="none", severity="none", blocked=False)
    assert review(answering(parsed)) is PhotoVerdict.REJECTED


def test_not_a_hazard_is_rejected_even_if_marked_blocked():
    assert review(answering(assessment(is_sidewalk_hazard=False))) is PhotoVerdict.REJECTED


def test_hazard_that_is_still_passable_is_rejected():
    parsed = assessment(kind="ice", severity="moderate", blocked=False)
    assert review(answering(parsed)) is PhotoVerdict.REJECTED


def test_blocked_hazard_with_low_confidence_is_rejected():
    assert review(answering(assessment(confidence="low"))) is PhotoVerdict.REJECTED


def test_severity_can_be_none_for_non_hazards():
    parsed = assessment(is_sidewalk_hazard=False, kind="none", severity="none", blocked=False)
    assert parsed.severity == "none"


# --- Failures become UNAVAILABLE (report stays pending) -----------------------


@pytest.mark.parametrize(
    "error",
    [
        anthropic.APIConnectionError(request=REQUEST),
        anthropic.APITimeoutError(request=REQUEST),
        anthropic.InternalServerError(
            "overloaded",
            response=httpx2.Response(529, request=REQUEST),
            body=None,
        ),
    ],
    ids=["connection", "timeout", "status"],
)
def test_api_error_is_unavailable(error):
    assert review(FakeClient(error)) is PhotoVerdict.UNAVAILABLE


def test_unexpected_client_exception_is_unavailable():
    assert review(FakeClient(RuntimeError("boom"))) is PhotoVerdict.UNAVAILABLE


def test_refusal_is_unavailable():
    assert review(answering(None, stop_reason="refusal")) is PhotoVerdict.UNAVAILABLE


def test_refusal_is_unavailable_even_with_parsed_output():
    assert review(answering(assessment(), stop_reason="refusal")) is PhotoVerdict.UNAVAILABLE


def test_missing_parsed_output_is_unavailable():
    assert review(answering(None, stop_reason="max_tokens")) is PhotoVerdict.UNAVAILABLE


def test_unknown_image_type_is_unavailable_without_calling_claude():
    client = answering(assessment())
    assert review(client, GIF) is PhotoVerdict.UNAVAILABLE
    assert client.messages.calls == []


def test_empty_photo_is_unavailable_without_calling_claude():
    client = answering(assessment())
    assert review(client, b"") is PhotoVerdict.UNAVAILABLE
    assert client.messages.calls == []


def test_oversized_photo_is_unavailable_without_calling_claude():
    client = answering(assessment())
    too_big = JPEG + b"\x00" * MAX_IMAGE_BYTES
    assert review(client, too_big) is PhotoVerdict.UNAVAILABLE
    assert client.messages.calls == []


def test_unavailable_reason_is_logged_without_image_bytes(caplog):
    with caplog.at_level("WARNING", logger="app.photo_review"):
        review(FakeClient(anthropic.APIConnectionError(request=REQUEST)))
    assert "APIConnectionError" in caplog.text
    assert base64.standard_b64encode(JPEG).decode() not in caplog.text


# --- Media type detection ---------------------------------------------------


@pytest.mark.parametrize(
    ("photo", "media_type"),
    [(JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp"), (GIF, None), (b"", None)],
    ids=["jpeg", "png", "webp", "gif", "empty"],
)
def test_detect_media_type(photo, media_type):
    assert detect_media_type(photo) == media_type


def test_riff_that_is_not_webp_is_unknown():
    assert detect_media_type(b"RIFF\x24\x00\x00\x00WAVEfmt ") is None


# --- The request sent to Claude ------------------------------------------------


@pytest.mark.parametrize(
    ("photo", "media_type"),
    [(JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp")],
    ids=["jpeg", "png", "webp"],
)
def test_request_uses_model_and_detected_media_type(photo, media_type):
    client = answering(assessment())

    review(client, photo)

    (call,) = client.messages.calls
    assert call["model"] == MODEL == "claude-opus-5-5"
    assert call["output_format"] is PhotoAssessment
    assert call["output_config"] == {"effort": "medium"}
    assert "thinking" not in call and "temperature" not in call
    image, text = call["messages"][0]["content"]
    assert image["source"] == {
        "type": "base64",
        "media_type": media_type,
        "data": base64.standard_b64encode(photo).decode("utf-8"),
    }
    assert text["type"] == "text"


def test_request_uses_timeout_and_one_retry():
    client = answering(assessment())

    make_claude_reviewer(client, timeout_s=7.5)(JPEG)

    assert client.options == {"timeout": 7.5, "max_retries": 1}


def test_default_client_is_created_lazily(monkeypatch):
    created: list[FakeClient] = []

    def fake_anthropic():
        created.append(answering(assessment()))
        return created[-1]

    monkeypatch.setattr(anthropic, "Anthropic", fake_anthropic)

    reviewer = make_claude_reviewer()
    assert created == []

    assert reviewer(JPEG) is PhotoVerdict.CONFIRMED
    assert reviewer(PNG) is PhotoVerdict.CONFIRMED
    assert len(created) == 1


def test_missing_api_key_is_unavailable(monkeypatch):
    def no_key():
        raise anthropic.AnthropicError("api_key client option must be set")

    monkeypatch.setattr(anthropic, "Anthropic", no_key)

    assert make_claude_reviewer()(JPEG) is PhotoVerdict.UNAVAILABLE
