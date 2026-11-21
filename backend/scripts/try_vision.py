"""Throwaway spike: see what Claude vision says about sidewalk photos.

Not part of the API. Prints one structured result per photo so you can judge
how reliable the model is before deciding who may mark a sidewalk blocked.

Usage (from backend/, with ANTHROPIC_API_KEY in backend/.env):
    uv run --env-file .env python scripts/try_vision.py path/to/photos
"""

import base64
import sys
from pathlib import Path
from typing import Literal

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5-5"
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # API limit for base64 images

PROMPT = (
    "You are assessing a photo submitted as a winter sidewalk hazard report in Boston. "
    "Judge only what is visible in the photo. If it does not show a sidewalk or walkway, "
    "set is_sidewalk_hazard to false and kind to 'none'. 'blocked' means a pedestrian "
    "cannot get through at all. 'accessibility_issue' means walkable on foot but not "
    "for a wheelchair, walker, or stroller."
)


class PhotoAssessment(BaseModel):
    is_sidewalk_hazard: bool
    kind: Literal["snow", "ice", "slush", "puddle", "obstruction", "none"]
    severity: Literal["minor", "moderate", "severe"]
    blocked: bool
    confidence: Literal["low", "medium", "high"]
    accessibility_issue: bool
    description: str


def assess(client: anthropic.Anthropic, photo: Path) -> str:
    data = photo.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        return "SKIPPED: larger than 5 MB"
    image = {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": MEDIA_TYPES[photo.suffix.lower()],
            "data": base64.standard_b64encode(data).decode("utf-8"),
        },
    }
    response = client.messages.parse(
        model=MODEL,
        max_tokens=4000,
        output_config={"effort": "medium"},
        messages=[{"role": "user", "content": [image, {"type": "text", "text": PROMPT}]}],
        output_format=PhotoAssessment,
    )
    if response.stop_reason == "refusal":
        return "REFUSED by the model"
    if response.parsed_output is None:
        return f"NO RESULT (stop_reason={response.stop_reason})"
    return response.parsed_output.model_dump_json(indent=2)


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/try_vision.py <photo folder>")
    photos = sorted(p for p in Path(sys.argv[1]).iterdir() if p.suffix.lower() in MEDIA_TYPES)
    if not photos:
        sys.exit("No .jpg/.jpeg/.png/.webp photos found in that folder.")

    client = anthropic.Anthropic()
    for photo in photos:
        try:
            result = assess(client, photo)
        except anthropic.APIStatusError as error:
            result = f"API ERROR {error.status_code}: {error.message}"
        except anthropic.APIConnectionError as error:
            result = f"CONNECTION ERROR: {error}"
        print(f"=== {photo.name} ===\n{result}\n")


if __name__ == "__main__":
    main()
