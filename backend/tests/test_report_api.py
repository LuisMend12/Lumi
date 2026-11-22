"""Report endpoints: POST /reports, votes, nearby segments and the report list."""

import logging
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.config import MAX_PHOTO_BYTES
from app.main import SIGN_IN_INVALID, SIGN_IN_REQUIRED, create_app
from app.reports import PhotoVerdict
from app.routing import RouteMode
from tests.conftest import auth_header
from tests.test_photo_review import assessment, mastra  # noqa: F401  (`mastra` is a fixture)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 64
GIF = b"GIF89a" + b"\x00" * 64

# Midpoints of the test graph's segments (see conftest.py).
NEAR = {
    "A-B": (42.3500, -71.1074),
    "B-D": (42.3500, -71.1062),
    "A-C": (42.3495, -71.1074),
    "C-D": (42.3495, -71.1062),
}
A_TO_D = {"start_lat": 42.3500, "start_lon": -71.1080, "end_lat": 42.3500, "end_lon": -71.1056}
DOWNTOWN = (42.3601, -71.0589)


def reviewer(*verdicts: PhotoVerdict):
    """Fake photo agent returning the given verdicts in turn (the last one repeats)."""
    queue = list(verdicts)
    return lambda photo: queue.pop(0) if len(queue) > 1 else queue[0]


def make_client(street_graph, **kwargs) -> TestClient:
    return TestClient(create_app(graph=street_graph, **kwargs))


@pytest.fixture
def confirming(street_graph):
    with make_client(street_graph, review_photo=reviewer(PhotoVerdict.CONFIRMED)) as client:
        yield client


def report(client, user="alice", where=NEAR["A-B"], photo=JPEG, filename="photo.jpg"):
    lat, lon = where
    return client.post(
        "/reports",
        data={"lat": str(lat), "lon": str(lon)},
        files={"photo": (filename, photo, "application/octet-stream")},
        headers=auth_header(user) if user else {},
    )


def vote(client, segment_id, user, blocked, where=None):
    lat, lon = where or NEAR[segment_id]
    return client.post(
        f"/segments/{segment_id}/votes",
        json={"blocked": blocked, "lat": lat, "lon": lon},
        headers=auth_header(user) if user else {},
    )


# --- POST /reports -----------------------------------------------------------


def test_confirmed_photo_blocks_the_nearest_segment(confirming):
    response = report(confirming, where=(42.35003, -71.1074))  # 3 m from A-B

    assert response.status_code == 201
    body = response.json()
    assert body["report_id"].startswith("r_")
    assert body == {
        "report_id": body["report_id"],
        "segment_id": "A-B",
        "outcome": "status_changed",
        "segment_status": "blocked",
    }


def test_photo_on_an_already_blocked_segment_is_a_vote(confirming):
    report(confirming, user="alice")

    response = report(confirming, user="bob")

    assert response.status_code == 201
    assert response.json()["outcome"] == "vote_recorded"
    assert response.json()["segment_status"] == "blocked"


def test_rejected_photo_is_unverified_and_leaves_segment_open(street_graph):
    with make_client(street_graph, review_photo=reviewer(PhotoVerdict.REJECTED)) as client:
        response = report(client)

    assert response.status_code == 201
    assert response.json()["outcome"] == "unverified"
    assert response.json()["segment_status"] == "open"


def test_default_reviewer_uses_mastra_and_confirms_a_blocked_photo(street_graph, mastra, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LUMI_MASTRA_URL", mastra.url)

    with make_client(street_graph) as client:
        response = report(client)

    assert response.status_code == 201
    assert response.json()["outcome"] == "status_changed"
    assert response.json()["segment_status"] == "blocked"
    assert [r["path"] for r in mastra.requests] == ["/review"]


def test_default_reviewer_marks_a_clear_photo_unverified(street_graph, mastra, monkeypatch):  # noqa: F811
    monkeypatch.setenv("LUMI_MASTRA_URL", mastra.url)
    mastra.answer(assessment(is_sidewalk_hazard=False, kind="none", severity="none", blocked=False))

    with make_client(street_graph) as client:
        response = report(client)

    assert response.json()["outcome"] == "unverified"
    assert response.json()["segment_status"] == "open"


def test_with_mastra_down_reports_stay_pending_and_a_warning_is_logged(street_graph, caplog):
    # conftest points LUMI_MASTRA_URL at a closed port.
    with caplog.at_level(logging.WARNING), make_client(street_graph) as client:
        response = report(client)

    assert response.status_code == 201
    assert response.json()["outcome"] == "pending"
    assert response.json()["segment_status"] == "open"
    assert any("Photo review unavailable" in r.getMessage() for r in caplog.records)


def test_reviewer_that_crashes_counts_as_unavailable(street_graph):
    def broken(photo):
        raise TimeoutError("agent timed out")

    with make_client(street_graph, review_photo=broken) as client:
        response = report(client)

    assert response.status_code == 201
    assert response.json()["outcome"] == "pending"


@pytest.mark.parametrize("photo", [JPEG, PNG, WEBP], ids=["jpeg", "png", "webp"])
def test_jpeg_png_and_webp_are_accepted_by_content_not_filename(confirming, photo):
    response = report(confirming, photo=photo, filename="upload.bin")

    assert response.status_code == 201


def test_unsupported_file_type_is_415(confirming):
    response = report(confirming, photo=GIF, filename="photo.jpg")

    assert response.status_code == 415
    assert "JPEG, PNG or WebP" in response.json()["detail"]


def test_photo_over_5_mb_is_413(confirming):
    response = report(confirming, photo=JPEG + b"\x00" * MAX_PHOTO_BYTES)

    assert response.status_code == 413
    assert "5 MB" in response.json()["detail"]


def test_photo_of_exactly_5_mb_is_accepted(confirming):
    response = report(confirming, photo=JPEG + b"\x00" * (MAX_PHOTO_BYTES - len(JPEG)))

    assert response.status_code == 201


def test_report_outside_the_coverage_area_is_422(confirming):
    response = report(confirming, where=DOWNTOWN)

    assert response.status_code == 422
    assert "outside" in response.json()["detail"]


def test_report_without_sign_in_is_401(confirming):
    response = report(confirming, user=None)

    assert response.status_code == 401
    assert response.json()["detail"] == SIGN_IN_REQUIRED
    assert response.headers["www-authenticate"] == "Bearer"


def test_report_with_an_invalid_token_is_401(confirming):
    response = confirming.post(
        "/reports",
        data={"lat": str(NEAR["A-B"][0]), "lon": str(NEAR["A-B"][1])},
        files={"photo": ("photo.jpg", JPEG, "image/jpeg")},
        headers={"Authorization": "Bearer forged-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == SIGN_IN_INVALID


def test_old_x_user_id_header_is_no_longer_accepted(confirming):
    response = confirming.post(
        "/segments/A-B/votes", json={"blocked": True, "lat": NEAR["A-B"][0], "lon": NEAR["A-B"][1]},
        headers={"X-User-Id": "alice"},
    )

    assert response.status_code == 401


def test_writes_are_503_when_sign_in_is_not_configured(street_graph, monkeypatch):
    monkeypatch.setattr("app.main.clerk_verifier_from_env", lambda origins: None)

    with make_client(street_graph, review_photo=reviewer(PhotoVerdict.CONFIRMED)) as client:
        response = report(client)

    assert response.status_code == 503


def test_reads_work_without_sign_in(confirming):
    assert confirming.get("/reports").status_code == 200
    assert confirming.get("/route", params={**A_TO_D, "mode": "safer"}).status_code == 200


# --- POST /segments/{segment_id}/votes --------------------------------------------


def test_first_vote_is_recorded_without_changing_status(confirming):
    response = vote(confirming, "A-B", "u1", blocked=True)

    assert response.status_code == 200
    assert response.json() == {"outcome": "vote_recorded", "segment_status": "open"}


def test_fourth_user_flips_a_blocked_segment_open(confirming):
    report(confirming, user="reporter")
    for user in ["u1", "u2", "u3"]:
        assert vote(confirming, "A-B", user, blocked=False).json()["outcome"] == "vote_recorded"

    response = vote(confirming, "A-B", "u4", blocked=False)

    assert response.status_code == 200
    assert response.json() == {"outcome": "status_changed", "segment_status": "open"}


def test_user_with_too_many_blocked_votes_must_send_a_photo(confirming):
    for segment in ["A-B", "B-D", "A-C"]:
        vote(confirming, segment, "spammer", blocked=True)

    response = vote(confirming, "C-D", "spammer", blocked=True)

    assert response.status_code == 200
    assert response.json() == {"outcome": "photo_required", "segment_status": "open"}


def test_vote_from_more_than_50_m_away_is_403(confirming):
    response = vote(confirming, "A-B", "u1", blocked=True, where=NEAR["C-D"])  # about 74 m from A-B

    assert response.status_code == 403
    assert "50 m" in response.json()["detail"]


def test_vote_on_unknown_segment_is_404(confirming):
    response = vote(confirming, "A-D", "u1", blocked=True, where=NEAR["A-B"])

    assert response.status_code == 404


def test_vote_without_user_id_is_401(confirming):
    response = vote(confirming, "A-B", None, blocked=True)

    assert response.status_code == 401


def test_vote_with_missing_fields_is_422(confirming):
    response = confirming.post("/segments/A-B/votes", json={"blocked": True}, headers=auth_header("u1"))

    assert response.status_code == 422


# --- GET /segments/nearby -----------------------------------------------------------


def test_nearby_lists_reported_segments_within_50_m(confirming):
    report(confirming, where=NEAR["A-B"])  # blocked
    vote(confirming, "C-D", "u1", blocked=True)  # reported, still open

    response = confirming.get("/segments/nearby", params={"lat": 42.35003, "lon": -71.1074})

    assert response.status_code == 200
    assert response.json() == [
        {
            "segment_id": "A-B",
            "status": "blocked",
            "coordinates": [[42.3500, -71.1080], [42.3500, -71.1068]],
        }
    ]


def test_nearby_skips_segments_nobody_reported(confirming):
    response = confirming.get("/segments/nearby", params={"lat": NEAR["A-B"][0], "lon": NEAR["A-B"][1]})

    assert response.status_code == 200
    assert response.json() == []


def test_nearby_includes_open_segments_with_votes(confirming):
    vote(confirming, "C-D", "u1", blocked=True)

    response = confirming.get("/segments/nearby", params={"lat": NEAR["C-D"][0], "lon": NEAR["C-D"][1]})

    assert [(s["segment_id"], s["status"]) for s in response.json()] == [("C-D", "open")]


# --- GET /reports ----------------------------------------------------------------


def test_reports_lists_confirmed_unverified_and_pending_separately(street_graph):
    verdicts = reviewer(PhotoVerdict.CONFIRMED, PhotoVerdict.REJECTED, PhotoVerdict.UNAVAILABLE)
    with make_client(street_graph, review_photo=verdicts) as client:
        ids = {
            "confirmed": report(client, where=NEAR["A-B"]).json()["report_id"],
            "unverified": report(client, where=NEAR["C-D"]).json()["report_id"],
            "pending": report(client, where=NEAR["B-D"]).json()["report_id"],
        }
        response = client.get("/reports")

    assert response.status_code == 200
    listed = {item["verification"]: item for item in response.json()}
    assert set(listed) == {"confirmed", "unverified", "pending"}
    assert {v: item["report_id"] for v, item in listed.items()} == ids
    assert listed["confirmed"]["segment_id"] == "A-B"
    assert listed["confirmed"]["location"] == pytest.approx([42.3500, -71.1074])  # segment midpoint
    assert all(item["simulated"] is False for item in listed.values())


def test_report_list_item_shape(confirming):
    before = datetime.now(UTC).replace(microsecond=0)
    report(confirming)

    [item] = confirming.get("/reports").json()

    assert set(item) == {"report_id", "segment_id", "location", "verification", "reported_at", "simulated"}
    assert item["reported_at"].endswith("Z")
    reported_at = datetime.fromisoformat(item["reported_at"])
    assert before <= reported_at <= datetime.now(UTC)


def test_confirmed_report_is_dropped_once_votes_reopen_the_segment(confirming):
    report(confirming, user="reporter")
    for user in ["u1", "u2", "u3", "u4"]:
        vote(confirming, "A-B", user, blocked=False)

    assert confirming.get("/reports").json() == []


def test_reports_empty_list(confirming):
    response = confirming.get("/reports")

    assert response.status_code == 200
    assert response.json() == []


# --- Routing reads the report rules ----------------------------------------------------


@pytest.mark.parametrize("mode", list(RouteMode))
def test_blockage_reported_through_the_api_changes_every_mode(confirming, mode):
    before = confirming.get("/route", params={**A_TO_D, "mode": mode.value}).json()
    report(confirming, where=NEAR["A-B"])

    after = confirming.get("/route", params={**A_TO_D, "mode": mode.value}).json()

    assert before["distance_m"] == pytest.approx(200.0)
    assert after["distance_m"] == pytest.approx(300.0)  # detour through C


def test_unverified_and_pending_reports_do_not_change_the_route(street_graph):
    verdicts = reviewer(PhotoVerdict.REJECTED, PhotoVerdict.UNAVAILABLE)
    with make_client(street_graph, review_photo=verdicts) as client:
        report(client, user="alice")
        report(client, user="bob")
        response = client.get("/route", params={**A_TO_D, "mode": "shortest"})

    assert response.json()["distance_m"] == pytest.approx(200.0)


def test_blockage_flipped_open_by_votes_returns_to_the_direct_route(confirming):
    report(confirming)
    for user in ["u1", "u2", "u3", "u4"]:
        vote(confirming, "A-B", user, blocked=False)

    response = confirming.get("/route", params={**A_TO_D, "mode": "safer"})

    assert response.json()["distance_m"] == pytest.approx(200.0)


def test_static_hazards_and_reported_blocks_are_merged(street_graph):
    from app.routing import Hazard, segment_key

    ice = {segment_key("C", "D"): [Hazard(kind="ice", severity=0.5, blocked=False)]}
    with make_client(street_graph, hazards=ice, review_photo=reviewer(PhotoVerdict.CONFIRMED)) as client:
        report(client, where=NEAR["A-B"])
        body = client.get("/route", params={**A_TO_D, "mode": "safer"}).json()

    assert body["distance_m"] == pytest.approx(300.0)  # A-B blocked, so through the ice on C-D
    assert [(h["location"], h["kind"]) for h in body["hazards"]] == [(pytest.approx(list(NEAR["C-D"])), "ice")]


# --- CORS ------------------------------------------------------------------


def test_cors_preflight_allows_post_with_authorization_header(confirming):
    response = confirming.options(
        "/reports",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_cors_origins_come_from_the_environment(street_graph, monkeypatch):
    monkeypatch.setenv("LUMI_FRONTEND_ORIGINS", "https://lumi.example, https://preview.lumi.example")

    with make_client(street_graph) as client:
        allowed = client.get("/health", headers={"Origin": "https://preview.lumi.example"})
        localhost = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert allowed.headers["access-control-allow-origin"] == "https://preview.lumi.example"
    assert "access-control-allow-origin" not in localhost.headers
