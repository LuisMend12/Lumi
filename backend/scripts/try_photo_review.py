"""Manual check: send a folder of sidewalk photos through the Mastra photo reviewer.

Not part of the API. For each photo it prints the assessment the Mastra service
returns (one model call per photo), plus the verdict the app's photo reviewer
would give, so you can judge how reliable the model is. The verdict rule lives
in `app/photo_review.py`.

Start the Mastra service first (`cd mastra && npm run dev`, with a Gemini key in
`mastra/.env`). Gemini's free tier may use what you send to improve Google's
products, so use photos without identifiable people.

Usage (from backend/):
    uv run python scripts/try_photo_review.py path/to/photos
Set LUMI_MASTRA_URL if the service isn't on http://localhost:4111.
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # make `app` importable

from app.photo_review import (  # noqa: E402
    DEFAULT_MASTRA_URL,
    MASTRA_URL_ENV,
    MAX_IMAGE_BYTES,
    ReviewUnavailable,
    detect_media_type,
    request_assessment,
    verdict_for,
)

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def assess(photo: Path, base_url: str) -> str:
    data = photo.read_bytes()
    if len(data) > MAX_IMAGE_BYTES:
        return "SKIPPED: larger than 5 MB"
    media_type = detect_media_type(data)
    if media_type is None:
        return "SKIPPED: not a JPEG, PNG or WebP file"
    try:
        assessment = request_assessment(data, media_type, base_url=base_url, timeout_s=20.0)
    except ReviewUnavailable as error:
        return f"UNAVAILABLE: {error}"
    verdict = verdict_for(assessment)  # the rule make_mastra_reviewer() applies
    return f"{assessment.model_dump_json(indent=2)}\nverdict: {verdict.value}"


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit("Usage: python scripts/try_photo_review.py <photo folder>")
    photos = sorted(p for p in Path(sys.argv[1]).iterdir() if p.suffix.lower() in PHOTO_SUFFIXES)
    if not photos:
        sys.exit("No .jpg/.jpeg/.png/.webp photos found in that folder.")

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    base_url = os.environ.get(MASTRA_URL_ENV) or DEFAULT_MASTRA_URL
    print(f"Mastra service: {base_url}\n")
    for photo in photos:
        print(f"=== {photo.name} ===\n{assess(photo, base_url)}\n")


if __name__ == "__main__":
    main()
