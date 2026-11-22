# Lumi photo review (Mastra)

A small [Mastra](https://mastra.ai/docs) service with one agent, `sidewalkReviewer`, that looks at a hazard report photo with Google Gemini (`google/gemini-3.8-flash`, free tier) and answers in a fixed JSON shape. The FastAPI backend calls it over HTTP (`backend/app/photo_review.py`) and decides the verdict itself.

```
FastAPI (make_mastra_reviewer) --POST /review--> Mastra (sidewalkReviewer) --> Gemini
```

Owned by the backend lane.

## Setup

Requires Node.js 22.18 or newer.

```bash
cd mastra
npm install
cp .env.example .env    # then paste your key into mastra/.env
```

Get a free key from [Google AI Studio](https://aistudio.google.com/apikey) and set `GOOGLE_GENERATIVE_AI_API_KEY` in `mastra/.env` (Mastra also accepts it as `GOOGLE_API_KEY`). `mastra/.env` is gitignored. Never commit it.

> **Privacy:** on Gemini's free tier, Google may use what you send to improve its products. Use demo photos without identifiable people (no faces, no license plates), and don't send real users' photos through a free-tier key.

## Run

```bash
npm run dev      # dev server with reload, on http://localhost:4111 (Studio on the same port)
```

Or build and run the bundled server:

```bash
npm run build    # bundles into .mastra/output (gitignored)
npm run start    # serves .mastra/output; same as: node .mastra/output/index.mjs
```

Set `PORT` to use another port, and point the backend at it with `LUMI_MASTRA_URL` (default `http://localhost:4111`).

Checks:

```bash
npm run typecheck
npm test         # route logic with Mastra's mock model: no key, no network
```

## Endpoint: `POST /review`

Request (JSON, at most 8 MB):

```json
{ "image_base64": "<base64 of the image bytes>", "media_type": "image/jpeg" }
```

- `media_type` is `image/jpeg`, `image/png` or `image/webp`, and must match the image bytes.
- The decoded image is at most 5 MB.

`200` response: exactly the assessment, with the same fields and enums as `PhotoAssessment` in `backend/app/photo_review.py`:

```json
{
  "is_sidewalk_hazard": true,
  "kind": "snow",
  "severity": "severe",
  "blocked": true,
  "confidence": "high",
  "accessibility_issue": true,
  "description": "Snowbank covers the whole sidewalk."
}
```

| Field | Values |
|---|---|
| `kind` | `snow`, `ice`, `slush`, `puddle`, `obstruction`, `none` |
| `severity` | `none`, `minor`, `moderate`, `severe` |
| `confidence` | `low`, `medium`, `high` |

Errors are JSON `{"error": "<code>", "message": "..."}`:

| Status | `error` | When |
|---|---|---|
| 400 | `invalid_request` | Body isn't JSON, fields are missing, or `image_base64` isn't base64 |
| 413 | `image_too_large` | Decoded image over 5 MB |
| 415 | `unsupported_media_type` | Not JPEG, PNG or WebP, or the bytes don't match `media_type` |
| 502 | `model_error` | The Gemini call failed (bad or missing key, rate limit, network) |
| 502 | `invalid_model_output` | Gemini's answer didn't match the schema |
| 504 | `model_timeout` | No answer within 15 s |

The backend treats every non-200 as "review unavailable": the report stays pending and doesn't affect routing.

Example:

```bash
curl -X POST http://localhost:4111/review -H "Content-Type: application/json" \
  -d "{\"image_base64\": \"$(base64 -w0 photo.jpg)\", \"media_type\": \"image/jpeg\"}"
```

Mastra also serves its built-in API under `/api` (for example `/api/agents/sidewalk-reviewer/generate`). The backend doesn't use it.

## Layout

```
src/mastra/index.ts                    Mastra instance and the POST /review route
src/mastra/review.ts                   prompt, request checks, zod schema, agent call
src/mastra/agents/sidewalk-reviewer.ts the agent and its Gemini model
test/review.test.ts                    route logic tests with a mock model
```
