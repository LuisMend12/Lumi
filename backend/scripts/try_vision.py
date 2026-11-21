"""Manual check: see what Claude vision says about sidewalk photos.

Not part of the API. Prints one structured result per photo, plus the verdict
the app's photo reviewer would give, so you can judge how reliable the model is.
The schema, prompt and verdict rules live in `app/photo_review.py`.

Each photo is one paid API call.

Usage (from backend/, with ANTHROPIC_API_KEY in backend/.env):
    uv run --env-file .env python scripts/try_vision.py path/to/photos
"""

import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make `app` importable

from app.photo_review import (  # noqa: E402
    MAX_IMAGE_BYTES,
    build_request,
    detect_media_type,
    verdict_for,
)

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def assess(client: anthropic.Anthropic, photo: Path) -> str:
    data = photo.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        return "SKIPPED: larger than 5 MB"
    media_type = detect_media_type(data)
    if media_type is None:
        return "SKIPPED: not a JPEG, PNG or WebP file"
    response = client.messages.parse(**build_request(data, media_type))
    if response.stop_reason == "refusal":
        return "REFUSED by the model"
    if response.parsed_output is None:
        return f"NO RESULT (stop_reason={response.stop_reason})"
    verdict = verdict_for(response.parsed_output)
    return f"{response.parsed_output.model_dump_json(indent=2)}\nverdict: {verdict.value}"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/try_vision.py <photo folder>")
    photos = sorted(p for p in Path(sys.argv[1]).iterdir() if p.suffix.lower() in PHOTO_SUFFIXES)
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
