"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { Fragment, useEffect, useRef } from "react";
import { Circle, CircleMarker, MapContainer, Marker, Polyline, TileLayer, Tooltip, useMap, useMapEvents, ZoomControl } from "react-leaflet";
import type { Hazard, LatLon, RouteMode, RouteOutcome } from "@/lib/api";
import { AMBER, AREA_CENTER, AREA_RADIUS_M, MODE_STYLES, NAVY, VERIFICATION_STYLES, hazardLabel } from "@/lib/modes";
import type { NearbySegment, Report } from "@/lib/reports-api";

type Props = {
  start: LatLon | null;
  end: LatLon | null;
  outcomes: Partial<Record<RouteMode, RouteOutcome>>;
  selectedMode: RouteMode;
  reports: Report[];
  nearbySegment: NearbySegment | null;
  onMapClick: (point: LatLon) => void;
  onSelectRoute: (mode: RouteMode) => void;
};

// Lettered pins for the start (A) and destination (B), styled in globals.css (#66).
const PIN_SIZE = 28;
function letterPin(letter: "A" | "B", variant: "start" | "end") {
  return L.divIcon({
    className: "",
    html: `<span class="lumi-pin lumi-pin--${variant}">${letter}</span>`,
    iconSize: [PIN_SIZE, PIN_SIZE],
    iconAnchor: [PIN_SIZE / 2, PIN_SIZE / 2],
  });
}
const START_PIN = letterPin("A", "start");
const END_PIN = letterPin("B", "end");

const NEARBY_HIGHLIGHT = AMBER; // a report state, so it keeps the report-state amber

function ReportMarker({ report }: { report: Report }) {
  const style = VERIFICATION_STYLES[report.verification];
  const label = `Report · ${style.label}`;
  return (
    <CircleMarker
      center={report.location}
      radius={6}
      pathOptions={{ color: style.stroke, weight: 2.5, dashArray: style.dashArray, fillColor: style.fill, fillOpacity: style.fillOpacity }}
    >
      {/* Simulated reports keep their badge on screen; real ones show the label on hover or tap. */}
      {/* "auto" flips the tooltip to whichever side has room, so it isn't clipped at the map edge. */}
      <Tooltip direction="auto" offset={[8, 0]} permanent={report.simulated}>
        {report.simulated ? `Simulated · ${label}` : label}
      </Tooltip>
    </CircleMarker>
  );
}

// When a new route appears (new start or end), fit it in view; switching modes or the
// 20 s refresh leaves the map where the visitor put it.
function FitRoute({ coordinates, routeKey }: { coordinates: LatLon[] | null; routeKey: string }) {
  const map = useMap();
  const fittedKey = useRef<string | null>(null);
  useEffect(() => {
    if (!coordinates || coordinates.length < 2 || fittedKey.current === routeKey) return;
    fittedKey.current = routeKey;
    map.fitBounds(L.latLngBounds(coordinates), { paddingTopLeft: [24, 64], paddingBottomRight: [24, 120] });
  }, [coordinates, routeKey, map]);
  return null;
}

function ClickHandler({ onMapClick }: { onMapClick: (point: LatLon) => void }) {
  useMapEvents({ click: (event) => onMapClick([event.latlng.lat, event.latlng.lng]) });
  return null;
}

const SNAP_LEG_STYLE = { color: NAVY, weight: 2, dashArray: "4 6", opacity: 0.8 };

function SnapLeg({ tapped, snapped }: { tapped: LatLon | null; snapped: LatLon | undefined }) {
  if (!tapped || !snapped) return null;
  return <Polyline positions={[tapped, snapped]} pathOptions={SNAP_LEG_STYLE} interactive={false} />;
}

function HazardMarker({ hazard }: { hazard: Hazard }) {
  if (!hazard.location) return null; // older backend responses have no location
  const style = VERIFICATION_STYLES[hazard.verification ?? "confirmed"];
  return (
    <CircleMarker
      center={hazard.location}
      radius={9}
      pathOptions={{ color: style.stroke, weight: 3, dashArray: style.dashArray, fillColor: style.fill, fillOpacity: style.fillOpacity }}
    >
      <Tooltip direction="auto" offset={[0, -8]} permanent>
        {hazardLabel(hazard)}
      </Tooltip>
    </CircleMarker>
  );
}

export default function RouteMap({
  start,
  end,
  outcomes,
  selectedMode,
  reports,
  nearbySegment,
  onMapClick,
  onSelectRoute,
}: Props) {
  // Draw the selected route last so it sits on top where routes overlap.
  const drawOrder = (Object.keys(outcomes) as RouteMode[]).sort(
    (a, b) => Number(a === selectedMode) - Number(b === selectedMode),
  );
  const selected = outcomes[selectedMode];
  const selectedRoute = selected?.status === "ok" ? selected.route : null;

  return (
    <MapContainer center={AREA_CENTER} zoom={15} className="h-full w-full" zoomControl={false}>
      {/* Top-right, so the LIVE label owns the top-left (#68). */}
      <ZoomControl position="topright" />
      {/* OpenStreetMap tiles (no API key), muted into the palette by a filter on the tile layer
          in globals.css, so routes and reports carry the colour (#68). */}
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Circle
        center={AREA_CENTER}
        radius={AREA_RADIUS_M}
        pathOptions={{ color: NAVY, weight: 1.5, dashArray: "6 6", fillOpacity: 0.04 }}
        interactive={false}
      />
      <ClickHandler onMapClick={onMapClick} />
      <FitRoute coordinates={selectedRoute?.coordinates ?? null} routeKey={`${start}|${end}`} />
      {reports.map((report) => (
        <ReportMarker key={report.report_id} report={report} />
      ))}
      {nearbySegment && (
        <Polyline
          positions={nearbySegment.coordinates}
          pathOptions={{ color: NEARBY_HIGHLIGHT, weight: 10, opacity: 0.85, lineCap: "round" }}
          interactive={false}
        />
      )}
      {drawOrder.map((mode) => {
        const outcome = outcomes[mode];
        if (outcome?.status !== "ok") return null;
        const isSelected = mode === selectedMode;
        const style = MODE_STYLES[mode];
        const weight = isSelected ? 7 : 4;
        return (
          <Fragment key={mode}>
            {/* An underlay per mode keeps every line legible on the pale basemap: navy under the pale
                Shortest line, white under the darker ones. */}
            <Polyline
              positions={outcome.route.coordinates}
              pathOptions={{
                color: style.casing.color,
                weight: weight + 5,
                opacity: style.casing.opacity * (isSelected ? 1 : 0.7),
                lineCap: "round",
              }}
              interactive={false}
            />
            <Polyline
              positions={outcome.route.coordinates}
              pathOptions={{
                color: style.color,
                weight,
                opacity: isSelected ? 1 : 0.75,
                dashArray: style.dashArray,
                lineCap: "round",
              }}
              eventHandlers={{ click: () => onSelectRoute(mode) }}
            />
          </Fragment>
        );
      })}
      <SnapLeg tapped={start} snapped={selectedRoute?.snapped_start} />
      <SnapLeg tapped={end} snapped={selectedRoute?.snapped_end} />
      {selectedRoute?.hazards.map((hazard, i) => (
        <HazardMarker key={hazard.segment_id ?? i} hazard={hazard} />
      ))}
      {start && <Marker position={start} icon={START_PIN} keyboard={false} title="Start (A)" />}
      {end && <Marker position={end} icon={END_PIN} keyboard={false} title="Destination (B)" />}
    </MapContainer>
  );
}
