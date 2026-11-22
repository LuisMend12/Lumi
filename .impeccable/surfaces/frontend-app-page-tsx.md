---
version: 1
slug: "frontend-app-page-tsx"
primary_target: "frontend/app/page.tsx"
related_targets: ["frontend/components/RouteMap.tsx"]
---

# Surface: Lumi map page (frontend/app/page.tsx)

**Mode:** Operate. The visitor picks and compares winter walking routes, reports or confirms blocked sidewalks.
**Audience and job:** BU students on foot, phone in hand, in winter; judges for a minute. Pick a route in seconds; see that people's reports changed it.
**Constraints:** light blue / white / navy palette (binding); never call a route safe; every report shows its verification state; simulated data always labeled; keyboard and screen-reader paths for setting a route.

## Direction contract

THESIS: Lumi reports the sidewalks the way Boston TV reports a snowstorm: live, bold, always labeled. It refuses the category default of a grey map app with a white bottom sheet and one blue accent.

OWN-WORLD: Storm Center. Navy #0b2545, storm blue #1d4e89, sky #8ecae6, mist #eaf4fa, white; amber and red only as report states. Barlow Condensed in bold caps for names, chyrons and numbers, Barlow for reading; tabular figures everywhere. Mode cards are lower-third chyrons that flood with their mode's colour when chosen; verification is a mark in a fixed cell (filled confirmed, hollow unverified, dotted under review). A muted light basemap so routes and reports carry the colour.

STORY: The visitor sees the map and a LIVE label, picks a start and destination, compares three chyrons, reads that Safer avoids reports, watches the live report crawl, and reports or confirms a sidewalk.

FIRST VIEWPORT: Phone: map on top with a LIVE chip top-left and zoom top-right, the report crawl as a navy strip along the map's bottom edge, the Report button above it; sheet below with the condensed wordmark, From/To, and the three chyrons, the selected one showing its minutes at poster scale. Desktop: same, sheet as a left column.

FORM: Storm Center, position 7 on the ordered list (Boston TV snowstorm coverage); seed:620cfacec9992f8f. Raises: tabular figures (Datamatics), poster-scale minutes (Metro), fixed-cell verification marks (Timetable), mode colour floods its chyron (Character Goods).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- Reports carry no street names yet, so the crawl names the state and time, not the place.
