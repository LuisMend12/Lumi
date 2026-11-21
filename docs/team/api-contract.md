# Lumi API contract

**Status:** proposed. Both of you must agree on it before the report endpoints and report UI go past mocks.
**Why it exists:** the backend and frontend are built at the same time. The frontend codes against this contract using mock data, and the backend makes it real. If either side needs to change it, edit this file in a PR that both of you review.

`GET /route` and `GET /health` already exist. Everything marked **new** is planned.

## Conventions

- Coordinates are `[lat, lon]` arrays, matching what `/route` returns today.
- `segment_id` is a string `"<u>-<v>"`, where `u` and `v` are the two OSM node IDs of the sidewalk segment with the smaller one first. Both walking directions share one ID.
- Times are ISO 8601 UTC strings, for example `"2026-11-21T18:04:00Z"`.
- Until login exists, the client sends a temporary `X-User-Id: <any stable string>` header on every write. The frontend can generate one and keep it in `localStorage`. The real ID comes from the login provider later (still undecided).
- Errors come back as `{"detail": "<message a person can read>"}` with the status codes listed under each endpoint.

## `GET /route` (exists; small additions)

The response stays as today, with these additions:

```json
{
  "mode": "safer",
  "mode_description": "Safer: ...",
  "distance_m": 951.7,
  "coordinates": [[42.3504, -71.1060], "..."],
  "snapped_start": [42.3505, -71.1058],
  "snapped_end": [42.3490, -71.0950],
  "hazards": [
    {
      "segment_id": "61326726-61340937",
      "location": [42.3497, -71.1001],
      "kind": "ice",
      "severity": 0.6,
      "blocked": false,
      "verification": "confirmed"
    }
  ]
}
```

- **New** `snapped_start` / `snapped_end`: the intersections the route actually starts and ends at. The frontend draws a dashed line from the point the user tapped to each of these.
- **New** in each hazard: `segment_id`, `location` (the segment midpoint, where the warning goes on the map) and `verification`. `verification` is `confirmed` today because only confirmed blocks reach routing.
- **New** error: `422` "Start and destination are too close" when both points snap to the same intersection.

## `POST /reports` (new): report a blocked sidewalk with a photo

The request is `multipart/form-data` with these fields:

| Field | Type | Notes |
|---|---|---|
| `lat`, `lon` | number | Where the user is reporting |
| `photo` | file | JPEG, PNG or WebP, at most 5 MB |

`201` response:

```json
{
  "report_id": "r_8f2c",
  "segment_id": "61326726-61340937",
  "outcome": "status_changed",
  "segment_status": "blocked"
}
```

`outcome` is one of:
- `status_changed`: the agent confirmed the photo, so the segment is now blocked.
- `vote_recorded`: the segment was already blocked.
- `unverified`: the agent didn't see a blockage. The report is shown on the map as unverified and doesn't affect routing.
- `pending`: the agent couldn't review the photo right now. It will be retried, and the report doesn't affect routing meanwhile.

Errors:
- `413`: the photo is too large.
- `415`: the file type isn't supported.
- `422`: the point is outside the coverage area.

## `POST /segments/{segment_id}/votes` (new): one-tap "Blocked or unblocked?"

```json
{ "blocked": false, "lat": 42.3497, "lon": -71.1001 }
```

`200` response: `{"outcome": "vote_recorded" | "status_changed" | "photo_required", "segment_status": "open" | "blocked"}`

- `photo_required`: this user has sent too many blocked reports recently, so the client must switch to the photo flow.

Errors:
- `403`: the user isn't within 50 m of the segment.
- `404`: the segment doesn't exist.

## `GET /segments/nearby?lat=&lon=` (new): what to ask the user about

This returns reported segments within 50 m, so the app can show the one-tap prompt.

```json
[
  { "segment_id": "61326726-61340937", "status": "blocked", "coordinates": [[42.3496, -71.1003], [42.3498, -71.0999]] }
]
```

## `GET /reports` (new): everything to draw on the map

```json
[
  {
    "report_id": "r_8f2c",
    "segment_id": "61326726-61340937",
    "location": [42.3497, -71.1001],
    "verification": "confirmed",
    "reported_at": "2026-11-21T18:04:00Z",
    "simulated": false
  }
]
```

- `verification` is one of `confirmed`, `unverified` or `pending`. The UI must label each one differently and must never present `unverified` or `pending` as fact.
- `simulated: true` marks reports created for the demo. The UI must show a visible "Simulated" badge on them.
