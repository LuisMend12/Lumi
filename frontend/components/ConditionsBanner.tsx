"use client";

import { useEffect, useState } from "react";
import { fetchConditions, type Conditions } from "@/lib/weather";

const REFRESH_MS = 10 * 60_000; // the NWS updates observations about once an hour

// A Storm Center chyron with what it's like outside right now, so the page feels
// live before anyone has reported anything. Hidden if the weather can't load.
export default function ConditionsBanner() {
  const [conditions, setConditions] = useState<Conditions | null>(null);

  useEffect(() => {
    let isActive = true;
    const load = () =>
      fetchConditions().then((result) => {
        if (isActive && result) setConditions(result);
      });
    load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      isActive = false;
      clearInterval(timer);
    };
  }, []);

  if (!conditions || (conditions.tempF === null && !conditions.description)) return null;

  const parts = [
    conditions.tempF !== null ? `${conditions.tempF}°F` : null,
    conditions.description,
    conditions.feelsLikeF !== null ? `Feels like ${conditions.feelsLikeF}°F` : null,
  ].filter((part): part is string => Boolean(part));

  return (
    <section aria-label="Boston weather now" className="font-display shrink-0 overflow-hidden rounded-lg bg-[var(--navy)] text-white">
      <div className="flex items-stretch">
        <span className="flex shrink-0 items-center bg-[var(--sky)] px-2.5 text-[13px] font-extrabold tracking-[0.12em] text-[var(--navy)] uppercase">
          Boston now
        </span>
        <p className="flex min-w-0 flex-wrap items-center gap-x-2 px-3 py-1.5 text-[15px] font-semibold tracking-wide">
          {parts.map((part, index) => (
            <span key={part} className="whitespace-nowrap">
              {index > 0 && (
                <span aria-hidden className="mr-2 opacity-40">
                  ·
                </span>
              )}
              {part}
            </span>
          ))}
        </p>
      </div>
      {conditions.alerts.length > 0 && (
        <p className="border-t border-white/15 bg-[var(--storm)] px-3 py-1.5 text-[14px] font-bold tracking-[0.06em] uppercase">
          NWS alert: {conditions.alerts.join(" · ")}
        </p>
      )}
    </section>
  );
}
