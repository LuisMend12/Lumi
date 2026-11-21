"use client";

import "leaflet/dist/leaflet.css";
import { Circle, CircleMarker, MapContainer, Polyline, TileLayer, Tooltip, useMapEvents } from "react-leaflet";
import type { Hazard, LatLon, RouteMode, RouteOutcome } from "@/lib/api";
import { AREA_CENTER, AREA_RADIUS_M, MODE_STYLES, NAVY, VERIFICATION_STYLES, hazardLabel } from "@/lib/modes";

type Props = {
  start: LatLon | null;
  end: LatLon | null;
  outcomes: Partial<Record<RouteMode, RouteOutcome>>;
  selectedMode: RouteMode;
  onMapClick: (point: LatLon) => void;
  onSelectRoute: (mode: RouteMode) => void;
};

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
      pathOptions={{ color: NAVY, weight: 2.5, fillColor: style.fill, fillOpacity: style.fillOpacity }}
    >
      <Tooltip direction="top" offset={[0, -8]} permanent>
        {hazardLabel(hazard)}
      </Tooltip>
    </CircleMarker>
  );
}

export default function RouteMap({ start, end, outcomes, selectedMode, onMapClick, onSelectRoute }: Props) {
  // Draw the selected route last so it sits on top where routes overlap.
  const drawOrder = (Object.keys(outcomes) as RouteMode[]).sort(
    (a, b) => Number(a === selectedMode) - Number(b === selectedMode),
  );
  const selected = outcomes[selectedMode];
  const selectedRoute = selected?.status === "ok" ? selected.route : null;

  return (
    <MapContainer center={AREA_CENTER} zoom={15} className="h-full w-full" zoomControl={false}>
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
      {drawOrder.map((mode) => {
        const outcome = outcomes[mode];
        if (outcome?.status !== "ok") return null;
        const isSelected = mode === selectedMode;
        const style = MODE_STYLES[mode];
        return (
          <Polyline
            key={mode}
            positions={outcome.route.coordinates}
            pathOptions={{
              color: style.color,
              weight: isSelected ? 7 : 4,
              opacity: isSelected ? 0.95 : 0.55,
              dashArray: style.dashArray,
              lineCap: "round",
            }}
            eventHandlers={{ click: () => onSelectRoute(mode) }}
          />
        );
      })}
      <SnapLeg tapped={start} snapped={selectedRoute?.snapped_start} />
      <SnapLeg tapped={end} snapped={selectedRoute?.snapped_end} />
      {selectedRoute?.hazards.map((hazard, i) => (
        <HazardMarker key={hazard.segment_id ?? i} hazard={hazard} />
      ))}
      {start && (
        <CircleMarker center={start} radius={8} pathOptions={{ color: "#fff", weight: 3, fillColor: NAVY, fillOpacity: 1 }} />
      )}
      {end && (
        <CircleMarker center={end} radius={8} pathOptions={{ color: NAVY, weight: 3, fillColor: "#fff", fillOpacity: 1 }} />
      )}
    </MapContainer>
  );
}
