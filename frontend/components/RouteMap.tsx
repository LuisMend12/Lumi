"use client";

import "leaflet/dist/leaflet.css";
import { Circle, CircleMarker, MapContainer, Polyline, TileLayer, useMapEvents } from "react-leaflet";
import type { LatLon, RouteMode, RouteOutcome } from "@/lib/api";
import { AREA_CENTER, AREA_RADIUS_M, MODE_STYLES, NAVY } from "@/lib/modes";

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

export default function RouteMap({ start, end, outcomes, selectedMode, onMapClick, onSelectRoute }: Props) {
  // Draw the selected route last so it sits on top where routes overlap.
  const drawOrder = (Object.keys(outcomes) as RouteMode[]).sort(
    (a, b) => Number(a === selectedMode) - Number(b === selectedMode),
  );

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
      {start && (
        <CircleMarker center={start} radius={8} pathOptions={{ color: "#fff", weight: 3, fillColor: NAVY, fillOpacity: 1 }} />
      )}
      {end && (
        <CircleMarker center={end} radius={8} pathOptions={{ color: NAVY, weight: 3, fillColor: "#fff", fillOpacity: 1 }} />
      )}
    </MapContainer>
  );
}
