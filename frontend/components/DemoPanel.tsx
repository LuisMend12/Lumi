"use client";

import { useState } from "react";
import type { Route } from "@/lib/api";
import { nearestSegment, pointHalfwayAlong, resetDemo, simulateBlock, simulateVotes } from "@/lib/demo-api";

type Props = {
  route: Route | null; // the selected route, if any
  onChanged: () => Promise<void>; // reload routes and reports
};

const BOT_COUNT = 4;

// Only rendered when the backend is in demo mode. Every action creates
// simulated data, which the map labels "Simulated".
export default function DemoPanel({ route, onChanged }: Props) {
  const [blockedSegment, setBlockedSegment] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  async function run(action: () => Promise<string>) {
    setIsBusy(true);
    try {
      setMessage(await action());
      await onChanged();
    } finally {
      setIsBusy(false);
    }
  }

  const blockOnRoute = () =>
    run(async () => {
      const point = route ? pointHalfwayAlong(route.coordinates) : null;
      if (!point) return "Pick a start and destination first.";
      const nearest = await nearestSegment(point);
      if (!nearest.ok) return nearest.message;
      const blocked = await simulateBlock(nearest.data.segment_id);
      if (!blocked.ok) return blocked.message;
      setBlockedSegment(nearest.data.segment_id);
      return "Simulated block added halfway along this route. Routes now avoid it.";
    });

  const botsSayClear = () =>
    run(async () => {
      if (!blockedSegment) return "Block a sidewalk first.";
      const result = await simulateVotes(blockedSegment, false, BOT_COUNT);
      if (!result.ok) return result.message;
      if (result.data.segment_status === "open") {
        setBlockedSegment(null);
        return `${result.data.votes_cast} simulated people said it's clear, so the sidewalk reopened.`;
      }
      return `${result.data.votes_cast} simulated votes recorded. The sidewalk is still blocked.`;
    });

  const reset = () =>
    run(async () => {
      const result = await resetDemo();
      if (!result.ok) return result.message;
      setBlockedSegment(null);
      return `Demo reset: removed ${result.data.removed} simulated reports and votes.`;
    });

  // Flat pills, not cards inside the panel; disabled stays readable (#68).
  const buttonClass =
    "font-display self-start rounded-full bg-[var(--navy)] px-4 py-2 text-[15px] font-bold tracking-[0.04em] text-white uppercase hover:bg-[var(--storm)] disabled:bg-transparent disabled:text-[var(--storm)] disabled:ring-1 disabled:ring-[var(--frost)]";

  return (
    <section aria-labelledby="demo-title" className="rounded-lg border border-[var(--frost)] bg-white p-3">
      <h2 id="demo-title" className="font-display flex items-center gap-2 text-base font-bold tracking-[0.04em] text-[var(--navy)] uppercase">
        <span className="rounded-sm bg-[var(--navy)] px-1.5 py-0.5 text-[12px] tracking-[0.1em] text-white">SIMULATED</span>
        Demo controls
      </h2>
      <p className="mt-0.5 text-xs text-pretty text-[var(--storm)]">Only shown in demo mode. Everything here is labeled Simulated.</p>
      <div className="mt-2 flex flex-col gap-2">
        <button type="button" className={buttonClass} disabled={isBusy || !route} onClick={blockOnRoute}>
          Block a sidewalk on this route
        </button>
        <button type="button" className={buttonClass} disabled={isBusy || !blockedSegment} onClick={botsSayClear}>
          {BOT_COUNT} bots say it&apos;s clear
        </button>
        <button type="button" className={buttonClass} disabled={isBusy} onClick={reset}>
          Reset demo
        </button>
      </div>
      {message && (
        <p role="status" className="mt-2 text-sm text-pretty text-[var(--navy)]">
          {message}
        </p>
      )}
    </section>
  );
}
