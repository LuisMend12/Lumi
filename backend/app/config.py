"""Coverage area and file locations. Change these to grow beyond BU."""

import os
from datetime import timedelta
from pathlib import Path

# Marsh Plaza, Boston University (Commonwealth Ave).
AREA_CENTER_LAT = 42.3504
AREA_CENTER_LON = -71.1060
AREA_RADIUS_M = 1500

BACKEND_DIR = Path(__file__).resolve().parent.parent
GRAPH_PATH = BACKEND_DIR / "data" / "bu_walk.graphml"

# A requested point farther than this from any graph intersection is
# treated as outside the coverage area instead of silently snapped.
MAX_SNAP_DISTANCE_M = 250

# Accessible mode (#33): a start or end reachable only by stairs moves to the
# nearest point of the step-free network if it's at most this far away.
MAX_STEP_FREE_SNAP_M = 100

# How strongly Safer mode avoids hazards: a segment with risk 1.0 costs
# (1 + SAFER_RISK_WEIGHT) times its length. Starting value; tune with data.
SAFER_RISK_WEIGHT = 4.0

# Browser origins allowed to call the API: the Next.js dev server by default.
# For a deployment, set LUMI_FRONTEND_ORIGINS to a comma-separated list.
FRONTEND_ORIGINS = ["http://localhost:3000"]


def frontend_origins() -> list[str]:
    """Allowed origins: LUMI_FRONTEND_ORIGINS if set, else FRONTEND_ORIGINS."""
    raw = os.environ.get("LUMI_FRONTEND_ORIGINS", "")
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return origins or list(FRONTEND_ORIGINS)


# Community reports (app/reports.py).
# Different users needed to flip a segment between blocked and open.
VOTES_TO_FLIP = 4
# A user with this many blocked reports inside the window must send a photo.
MAX_BLOCK_REPORTS_IN_WINDOW = 3
BLOCK_REPORT_WINDOW = timedelta(hours=24)

# How often pending photo reports are re-sent to the photo agent (#53).
PENDING_RETRY_INTERVAL_S = 30
# Each retry is a paid reviewer call, so a pending photo gets at most this many
# per server run; after that it stays "Under review" until the next restart.
MAX_PENDING_REVIEW_RETRIES = 10

# Report endpoints (app/main.py).
# A user must be this close to a segment to vote on it, and GET /segments/nearby
# returns reported segments within this distance.
NEARBY_RADIUS_M = 50
# Each photo report is a paid call to the photo reviewer (Gemini), so a user
# may send at most this many inside the window; more get 429 (#82).
MAX_PHOTO_REPORTS_IN_WINDOW = 5
PHOTO_REPORT_WINDOW = timedelta(hours=1)

# Largest photo POST /reports accepts (5 MiB).
MAX_PHOTO_BYTES = 5 * 1024 * 1024

# Demo mode (#38): LUMI_DEMO_MODE=1 adds /demo endpoints that act as simulated
# users "sim-1" ... "sim-N". Off by default; never enable it in production.
DEMO_MODE_ENV = "LUMI_DEMO_MODE"
DEMO_USER_PREFIX = "sim-"
DEMO_PHOTO_USER = "sim-photo"
MAX_DEMO_VOTERS = 10
