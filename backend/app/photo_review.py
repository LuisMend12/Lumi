"""Photo review: does a report photo show a blocked sidewalk?

The model call runs in the Mastra service (`mastra/` at the repo root): a
`sidewalkReviewer` agent on a free-tier Google Gemini model. This module sends
the photo to its `POST /review` endpoint and turns the assessment into a
`PhotoVerdict`. The confirm rule stays here, next to the report rules.

`make_mastra_reviewer()` returns a `PhotoReviewer` for `SegmentReports`.
It never raises. Anything that stops a real answer (connection errors,
timeouts, error responses, invalid JSON, unsupported or oversized images)
returns `UNAVAILABLE`, so the report stays pending and can be retried later.

The service URL comes from `LUMI_MASTRA_URL` (default `http://localhost:4111`).
"""

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from typing import Literal

from pydantic import BaseModel, ValidationError

from app.reports import PhotoReviewer, PhotoVerdict

logger = logging.getLogger(__name__)

DEFAULT_MASTRA_URL = "http://localhost:4111"  # Mastra's default port
MASTRA_URL_ENV = "LUMI_MASTRA_URL"
REVIEW_PATH = "/review"
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # same limit as the Mastra service

# Confidence levels that may confirm a blocked report.
CONFIRMING_CONFIDENCE = frozenset({"medium", "high"})


class PhotoAssessment(BaseModel):
    """The JSON body of a 200 response from `POST /review`."""

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


def build_request_body(photo: bytes, media_type: str) -> dict[str, str]:
    """JSON body for `POST /review` on the Mastra service."""
    return {
        "image_base64": base64.standard_b64encode(photo).decode("ascii"),
        "media_type": media_type,
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


class ReviewUnavailable(Exception):
    """The Mastra service gave no usable assessment. The message is safe to log."""


def request_assessment(
    photo: bytes, media_type: str, *, base_url: str, timeout_s: float
) -> PhotoAssessment:
    """Send one photo to `POST /review`. Raises `ReviewUnavailable` on any failure."""
    url = base_url.rstrip("/") + REVIEW_PATH
    request = urllib.request.Request(
        url,
        data=json.dumps(build_request_body(photo, media_type)).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        raise ReviewUnavailable(f"status {error.code}{_error_code(error)}") from None
    except TimeoutError:
        raise ReviewUnavailable(f"timed out after {timeout_s} s") from None
    except urllib.error.URLError as error:
        if isinstance(error.reason, TimeoutError):
            raise ReviewUnavailable(f"timed out after {timeout_s} s") from None
        raise ReviewUnavailable(f"cannot reach {url} ({type(error.reason).__name__})") from None
    except Exception as error:
        raise ReviewUnavailable(f"unexpected {type(error).__name__}") from None

    try:
        return PhotoAssessment.model_validate_json(raw)
    except ValidationError as error:
        # Pydantic reports invalid JSON as a validation error too.
        kinds = sorted({detail["type"] for detail in error.errors()})
        raise ReviewUnavailable(f"response is not a valid assessment ({', '.join(kinds)})") from None


def _error_code(error: urllib.error.HTTPError) -> str:
    """The service's `error` code from a JSON error body, if there is one."""
    try:
        code = json.loads(error.read()).get("error")
    except Exception:
        return ""
    return f", {code}" if isinstance(code, str) else ""


def make_mastra_reviewer(base_url: str | None = None, *, timeout_s: float = 20.0) -> PhotoReviewer:
    """A `PhotoReviewer` backed by the Mastra service's `POST /review`.

    Without `base_url`, the URL is read from `LUMI_MASTRA_URL` on each call,
    falling back to `http://localhost:4111`.
    """

    def review(photo: bytes) -> PhotoVerdict:
        media_type = detect_media_type(photo)
        if media_type is None:
            return _unavailable("unsupported image type (not JPEG, PNG or WebP)")
        if len(photo) > MAX_IMAGE_BYTES:
            return _unavailable(f"image is {len(photo)} bytes, over the {MAX_IMAGE_BYTES} limit")

        url = base_url or os.environ.get(MASTRA_URL_ENV) or DEFAULT_MASTRA_URL
        try:
            assessment = request_assessment(photo, media_type, base_url=url, timeout_s=timeout_s)
        except ReviewUnavailable as error:
            return _unavailable(str(error))
        except Exception as error:  # never raise into the report rules
            return _unavailable(f"unexpected {type(error).__name__}")
        return verdict_for(assessment)

    return review


def _unavailable(reason: str) -> PhotoVerdict:
    logger.warning("Photo review unavailable: %s", reason)
    return PhotoVerdict.UNAVAILABLE
