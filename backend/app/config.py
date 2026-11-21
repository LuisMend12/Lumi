"""Coverage area and file locations. Change these to grow beyond BU."""

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

# How strongly Safer mode avoids hazards: a segment with risk 1.0 costs
# (1 + SAFER_RISK_WEIGHT) times its length. Starting value; tune with data.
SAFER_RISK_WEIGHT = 4.0

# Browser origins allowed to call the API (the Next.js dev server).
FRONTEND_ORIGINS = ["http://localhost:3000"]

# Community reports (app/reports.py).
# Different users needed to flip a segment between blocked and open.
VOTES_TO_FLIP = 4
# A user with this many blocked reports inside the window must send a photo.
MAX_BLOCK_REPORTS_IN_WINDOW = 3
BLOCK_REPORT_WINDOW = timedelta(hours=24)
