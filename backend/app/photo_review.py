"""Photo review with Claude vision: does a report photo show a blocked sidewalk?

`make_claude_reviewer()` returns a `PhotoReviewer` for `SegmentReports`.
It never raises. Anything that stops a real answer (API errors, timeouts,
refusals, unparseable output, unsupported or oversized images) returns
`UNAVAILABLE`, so the report stays pending and can be retried later.

The API key comes from `ANTHROPIC_API_KEY` (put it in `backend/.env`).
"""

import base64
import logging
from typing import Any, Literal

import anthropic
from pydantic import BaseModel

from app.reports import PhotoReviewer, PhotoVerdict

logger = logging.getLogger(__name__)

MODEL = "claude-opus-5-5"
MAX_TOKENS = 4000
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # API limit for base64 images

PROMPT = (
    "You are assessing a photo submitted as a winter sidewalk hazard report in Boston. "
    "Judge only what is visible in the photo. If it does not show a sidewalk or walkway, "
    "or shows no hazard, set is_sidewalk_hazard to false, kind to 'none' and severity "
    "to 'none'. 'blocked' means a pedestrian cannot get through at all. "
    "'accessibility_issue' means walkable on foot but not for a wheelchair, walker, "
    "or stroller."
)

# Confidence levels that may confirm a blocked report.
CONFIRMING_CONFIDENCE = frozenset({"medium", "high"})


class PhotoAssessment(BaseModel):
    is_sidewalk_hazard: bool
    kind: Literal["snow", "ice", "slush", "puddle", "obstruction", "none"]
    severity: Literal["none", "minor", "moderate", "severe"]
    blocked: bool
    confidence: Literal["low", "medium", "high"]
    accessibility_issue: bool
    description: str


def detect_media_type(photo: bytes) -> str | None:
    """Image media type from the file's magic bytes, or None if unsupported."""
    if photo.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if photo.startswith(b"\x89PNG"):
        return "image/png"
    if len(photo) >= 12 and photo[:4] == b"RIFF" and photo[8:12] == b"WEBP":
        return "image/webp"
    return None


def build_request(photo: bytes, media_type: str) -> dict[str, Any]:
    """Keyword arguments for `client.messages.parse(...)`."""
    image = {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": base64.standard_b64encode(photo).decode("utf-8"),
        },
    }
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "output_config": {"effort": "medium"},
        "messages": [{"role": "user", "content": [image, {"type": "text", "text": PROMPT}]}],
        "output_format": PhotoAssessment,
    }


def verdict_for(assessment: PhotoAssessment) -> PhotoVerdict:
    """CONFIRMED only for a blocked sidewalk hazard seen with medium+ confidence."""
    if (
        assessment.is_sidewalk_hazard
        and assessment.blocked
        and assessment.confidence in CONFIRMING_CONFIDENCE
    ):
        return PhotoVerdict.CONFIRMED
    return PhotoVerdict.REJECTED


def make_claude_reviewer(
    client: anthropic.Anthropic | None = None, *, timeout_s: float = 20.0
) -> PhotoReviewer:
    """A `PhotoReviewer` backed by Claude vision.

    Without `client`, an `anthropic.Anthropic()` is created on the first call
    (it reads `ANTHROPIC_API_KEY`). Tests pass a fake client instead.
    """
    clients: list[Any] = [client] if client is not None else []

    def get_client() -> Any:
        if not clients:
            clients.append(anthropic.Anthropic())
        return clients[0]

    def review(photo: bytes) -> PhotoVerdict:
        media_type = detect_media_type(photo)
        if media_type is None:
            return _unavailable("unsupported image type (not JPEG, PNG or WebP)")
        if len(photo) > MAX_IMAGE_BYTES:
            return _unavailable(f"image is {len(photo)} bytes, over the {MAX_IMAGE_BYTES} limit")

        try:
            response = (
                get_client()
                .with_options(timeout=timeout_s, max_retries=1)
                .messages.parse(**build_request(photo, media_type))
            )
        except anthropic.APIError as error:
            status = getattr(error, "status_code", None)
            detail = f" (status {status})" if status is not None else ""
            return _unavailable(f"{type(error).__name__}{detail}")
        except Exception as error:  # never raise into the report rules
            return _unavailable(f"unexpected {type(error).__name__}")

        try:
            if response.stop_reason == "refusal":
                return _unavailable("model refused")
            parsed = response.parsed_output
            if parsed is None:
                return _unavailable(f"no parsed output (stop_reason={response.stop_reason})")
            return verdict_for(parsed)
        except Exception as error:
            return _unavailable(f"unexpected {type(error).__name__} reading the response")

    return review


def _unavailable(reason: str) -> PhotoVerdict:
    logger.warning("Photo review unavailable: %s", reason)
    return PhotoVerdict.UNAVAILABLE
