"use client";

import { useId } from "react";
import { LANDMARKS } from "@/lib/landmarks";

export const MY_LOCATION = "my-location";
export const MAP_POINT = "map-point";

type Props = {
  from: string; // a landmark id, MY_LOCATION, MAP_POINT, or "" for none
  to: string;
  isLocating: boolean;
  onFromChange: (choice: string) => void;
  onToChange: (choice: string) => void;
};

// A keyboard- and screen-reader-friendly way to set a route; tapping the map
// still works and shows up here as "Point on the map" (#67).
export default function RoutePicker({ from, to, isLocating, onFromChange, onToChange }: Props) {
  const fromId = useId();
  const toId = useId();
  const selectClass =
    "w-full rounded-xl border-2 border-[var(--frost)] bg-white px-3 py-2 text-sm text-[var(--navy)] focus-visible:border-[var(--navy)] focus-visible:outline-none";

  return (
    <div className="grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-2">
      <label htmlFor={fromId} className="font-display text-[15px] font-bold tracking-[0.05em] text-[var(--navy)] uppercase">
        From <span className="lumi-pin lumi-pin--start ml-1 scale-75 align-middle" aria-hidden>A</span>
      </label>
      <select id={fromId} className={selectClass} value={from} onChange={(event) => onFromChange(event.target.value)}>
        <option value="">Choose a start…</option>
        <option value={MY_LOCATION}>{isLocating ? "Finding your location…" : "My location"}</option>
        {from === MAP_POINT && <option value={MAP_POINT}>Point on the map</option>}
        {LANDMARKS.map((landmark) => (
          <option key={landmark.id} value={landmark.id}>
            {landmark.name}
          </option>
        ))}
      </select>

      <label htmlFor={toId} className="font-display text-[15px] font-bold tracking-[0.05em] text-[var(--navy)] uppercase">
        To <span className="lumi-pin lumi-pin--end ml-1 scale-75 align-middle" aria-hidden>B</span>
      </label>
      <select id={toId} className={selectClass} value={to} onChange={(event) => onToChange(event.target.value)}>
        <option value="">Choose a destination…</option>
        {to === MAP_POINT && <option value={MAP_POINT}>Point on the map</option>}
        {LANDMARKS.map((landmark) => (
          <option key={landmark.id} value={landmark.id}>
            {landmark.name}
          </option>
        ))}
      </select>
    </div>
  );
}
