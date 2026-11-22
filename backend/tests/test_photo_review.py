"""Mastra photo reviewer, tested against a tiny local HTTP server (no Mastra, no Gemini)."""

import base64
import json
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import get_args

import pytest

from app import photo_review
from app.photo_review import (
    DEFAULT_MASTRA_URL,
    MAX_IMAGE_BYTES,
    PhotoAssessment,
    build_request_body,
    detect_media_type,
    make_mastra_reviewer,
)
from app.reports import PhotoVerdict

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32
GIF = b"GIF89a" + b"\x00" * 32

MASTRA_REVIEW_TS = Path(__file__).resolve().parents[2] / "mastra" / "src" / "mastra" / "review.ts"


def assessment(**overrides) -> dict:
    fields = {
        "is_sidewalk_hazard": True,
        "kind": "snow",
        "severity": "severe",
        "blocked": True,
        "confidence": "high",
        "accessibility_issue": True,
        "description": "Snowbank covers the whole sidewalk.",
    }
    return fields | overrides


@dataclass
class FakeMastra:
    """What the fake service answers, and what it received."""

    url: str
    status: int = 200
    body: bytes = b""
    delay_s: float = 0.0
    requests: list[dict] = field(default_factory=list)

    def answer(self, payload: dict | str | bytes, status: int = 200) -> None:
        if isinstance(payload, dict):
            payload = json.dumps(payload)
        if isinstance(payload, str):
            payload = payload.encode()
        self.status, self.body = status, payload


@pytest.fixture
def mastra():
    """A local HTTP server on a free port standing in for the Mastra service."""
    fake = FakeMastra(url="")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            fake.requests.append(
                {
                    "path": self.path,
                    "content_type": self.headers.get("Content-Type"),
                    "body": json.loads(self.rfile.read(length)),
                }
            )
            time.sleep(fake.delay_s)
            self.send_response(fake.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(fake.body)))
            self.end_headers()
            self.wfile.write(fake.body)

        def log_message(self, *args):  # keep pytest output quiet
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    fake.answer(assessment())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield fake
    server.shutdown()
    server.server_close()


def review(mastra: FakeMastra, photo: bytes = JPEG, **kwargs) -> PhotoVerdict:
    return make_mastra_reviewer(mastra.url, **kwargs)(photo)


def closed_port_url() -> str:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    return f"http://127.0.0.1:{port}"  # nothing listens here once the socket closes


# --- Verdicts -------------------------------------------------------------


def test_blocked_hazard_with_high_confidence_is_confirmed(mastra):
    assert review(mastra) is PhotoVerdict.CONFIRMED


def test_blocked_hazard_with_medium_confidence_is_confirmed(mastra):
    mastra.answer(assessment(confidence="medium"))
    assert review(mastra) is PhotoVerdict.CONFIRMED


def test_photo_that_is_not_a_sidewalk_hazard_is_rejected(mastra):
    mastra.answer(assessment(is_sidewalk_hazard=False, kind="none", severity="none", blocked=False))
    assert review(mastra) is PhotoVerdict.REJECTED


def test_not_a_hazard_is_rejected_even_if_marked_blocked(mastra):
    mastra.answer(assessment(is_sidewalk_hazard=False))
    assert review(mastra) is PhotoVerdict.REJECTED


def test_hazard_that_is_still_passable_is_rejected(mastra):
    mastra.answer(assessment(kind="ice", severity="moderate", blocked=False))
    assert review(mastra) is PhotoVerdict.REJECTED


def test_blocked_hazard_with_low_confidence_is_rejected(mastra):
    mastra.answer(assessment(confidence="low"))
    assert review(mastra) is PhotoVerdict.REJECTED


# --- Failures become UNAVAILABLE (report stays pending) -----------------------


@pytest.mark.parametrize("status", [400, 413, 415, 500, 502, 504])
def test_error_status_is_unavailable(mastra, status):
    mastra.answer({"error": "model_error", "message": "The model call failed."}, status=status)
    assert review(mastra) is PhotoVerdict.UNAVAILABLE


def test_error_status_with_non_json_body_is_unavailable(mastra):
    mastra.answer("<html>Bad gateway</html>", status=502)
    assert review(mastra) is PhotoVerdict.UNAVAILABLE


def test_service_not_running_is_unavailable():
    assert make_mastra_reviewer(closed_port_url())(JPEG) is PhotoVerdict.UNAVAILABLE


def test_timeout_is_unavailable(mastra, caplog):
    mastra.delay_s = 1.0
    with caplog.at_level("WARNING", logger="app.photo_review"):
        assert review(mastra, timeout_s=0.2) is PhotoVerdict.UNAVAILABLE
    assert "timed out" in caplog.text


def test_invalid_json_is_unavailable(mastra):
    mastra.answer("I think it is snowy.")
    assert review(mastra) is PhotoVerdict.UNAVAILABLE


def test_empty_body_is_unavailable(mastra):
    mastra.answer(b"")
    assert review(mastra) is PhotoVerdict.UNAVAILABLE


@pytest.mark.parametrize(
    "payload",
    [
        assessment(kind="lava"),
        assessment(confidence="certain"),
        {k: v for k, v in assessment().items() if k != "blocked"},
        [assessment()],
    ],
    ids=["bad-kind", "bad-confidence", "missing-field", "not-an-object"],
)
def test_json_that_fails_validation_is_unavailable(mastra, payload):
    mastra.answer(json.dumps(payload))
    assert review(mastra) is PhotoVerdict.UNAVAILABLE


def test_unexpected_exception_is_unavailable(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(photo_review.urllib.request, "urlopen", boom)
    assert make_mastra_reviewer("http://mastra.test")(JPEG) is PhotoVerdict.UNAVAILABLE


def test_unknown_image_type_is_unavailable_without_a_request(mastra):
    assert review(mastra, GIF) is PhotoVerdict.UNAVAILABLE
    assert mastra.requests == []


def test_empty_photo_is_unavailable_without_a_request(mastra):
    assert review(mastra, b"") is PhotoVerdict.UNAVAILABLE
    assert mastra.requests == []


def test_oversized_photo_is_unavailable_without_a_request(mastra):
    too_big = JPEG + b"\x00" * MAX_IMAGE_BYTES
    assert review(mastra, too_big) is PhotoVerdict.UNAVAILABLE
    assert mastra.requests == []


def test_unavailable_reason_is_logged_without_image_bytes(mastra, caplog):
    mastra.answer({"error": "model_timeout", "message": "slow"}, status=504)
    with caplog.at_level("WARNING", logger="app.photo_review"):
        review(mastra)
    assert "status 504, model_timeout" in caplog.text
    assert base64.standard_b64encode(JPEG).decode() not in caplog.text


# --- The request sent to Mastra ------------------------------------------------


@pytest.mark.parametrize(
    ("photo", "media_type"),
    [(JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp")],
    ids=["jpeg", "png", "webp"],
)
def test_request_body_has_base64_image_and_detected_media_type(mastra, photo, media_type):
    review(mastra, photo)

    (request,) = mastra.requests
    assert request["path"] == "/review"
    assert request["content_type"] == "application/json"
    assert request["body"] == {
        "image_base64": base64.standard_b64encode(photo).decode("ascii"),
        "media_type": media_type,
    }
    assert request["body"] == build_request_body(photo, media_type)


def test_trailing_slash_in_base_url_is_ignored(mastra):
    make_mastra_reviewer(mastra.url + "/")(JPEG)
    assert mastra.requests[0]["path"] == "/review"


def test_url_comes_from_env_when_not_given(mastra, monkeypatch):
    monkeypatch.setenv("LUMI_MASTRA_URL", mastra.url)
    assert make_mastra_reviewer()(JPEG) is PhotoVerdict.CONFIRMED
    assert len(mastra.requests) == 1


def test_default_url_is_mastra_default_port(monkeypatch):
    monkeypatch.delenv("LUMI_MASTRA_URL", raising=False)
    seen: list[str] = []

    def fake_urlopen(request, timeout):
        seen.append(request.full_url)
        raise photo_review.urllib.error.URLError(ConnectionRefusedError())

    monkeypatch.setattr(photo_review.urllib.request, "urlopen", fake_urlopen)

    assert make_mastra_reviewer()(JPEG) is PhotoVerdict.UNAVAILABLE
    assert seen == [f"{DEFAULT_MASTRA_URL}/review"] == ["http://localhost:4111/review"]


def test_timeout_is_passed_to_urlopen(monkeypatch):
    timeouts: list[float] = []

    def fake_urlopen(request, timeout):
        timeouts.append(timeout)
        raise TimeoutError

    monkeypatch.setattr(photo_review.urllib.request, "urlopen", fake_urlopen)

    assert make_mastra_reviewer("http://mastra.test", timeout_s=7.5)(JPEG) is PhotoVerdict.UNAVAILABLE
    assert timeouts == [7.5]


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


# --- Contract with the Mastra service -----------------------------------------


def test_mastra_schema_matches_photo_assessment():
    """Every field and enum value here also appears in the Mastra zod schema."""
    source = MASTRA_REVIEW_TS.read_text(encoding="utf-8")
    schema = re.search(r"photoAssessmentSchema = z\.object\(\{(.*?)\}\);", source, re.S)
    assert schema, "photoAssessmentSchema not found in mastra/src/mastra/review.ts"
    body = schema.group(1)
    for name, info in PhotoAssessment.model_fields.items():
        line = re.search(rf"^\s*{name}: (.*)$", body, re.M)
        assert line, f"{name} missing from the Mastra schema"
        values = get_args(info.annotation)
        if values:
            assert set(re.findall(r"'([a-z]+)'", line.group(1))) == set(values), name
    assert len(re.findall(r"^\s*\w+: z\.", body, re.M)) == len(PhotoAssessment.model_fields)
