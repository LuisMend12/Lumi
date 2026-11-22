"use client";

import { useState } from "react";
import type { NearbySegment } from "@/lib/reports-api";

type Props = {
  segment: NearbySegment;
  isSending: boolean;
  message: string | null;
  onVote: (blocked: boolean) => void;
  onDismiss: () => void;
};

// Starts as a small chip so it never takes over the map; tapping it opens the
// one-tap question (#65). Bottom-left on phones (thumb reach), top-right on desktop.
export default function NearbyPrompt({ segment, isSending, message, onVote, onDismiss }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const question = segment.status === "blocked" ? "Is this sidewalk still blocked?" : "Is this sidewalk blocked?";
  // Clear of the report crawl and the Report button on phones, under the zoom control on desktop.
  const position = "absolute bottom-[7.5rem] left-4 z-[900] md:top-24 md:right-4 md:bottom-auto md:left-auto";

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        aria-expanded={false}
        className={`${position} flex items-center gap-2 rounded-full bg-white py-2 pr-4 pl-3 text-sm font-semibold text-[var(--navy)] shadow-[0_6px_18px_rgba(16,42,67,0.22)] hover:bg-[var(--snow)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--navy)]`}
      >
        <span className="h-2.5 w-2.5 rounded-full bg-[var(--amber)]" aria-hidden />
        Reported sidewalk near you
      </button>
    );
  }

  return (
    <div
      role="region"
      aria-label="Nearby sidewalk question"
      className={`${position} w-[min(20rem,calc(100%-2rem))] rounded-2xl bg-white p-4 shadow-[0_8px_24px_rgba(16,42,67,0.2)]`}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold text-[var(--navy)]">{question}</p>
        <button
          type="button"
          onClick={() => setIsOpen(false)}
          className="-mt-1 -mr-1 rounded-lg px-2 py-1.5 text-sm text-[var(--muted)] hover:bg-[var(--snow)]"
        >
          Later
        </button>
      </div>
      <p className="mt-1 text-xs text-[var(--muted)]">The sidewalk highlighted in amber is within 50 m of you.</p>
      {message ? (
        <p role="status" className="mt-3 rounded-lg bg-[var(--ice)] px-3 py-2 text-sm text-[var(--navy)]">
          {message}
        </p>
      ) : (
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            disabled={isSending}
            onClick={() => onVote(true)}
            className="rounded-xl bg-[var(--navy)] px-3 py-3 font-semibold text-white disabled:opacity-40"
          >
            Still blocked
          </button>
          <button
            type="button"
            disabled={isSending}
            onClick={() => onVote(false)}
            className="rounded-xl border-2 border-[var(--navy)] px-3 py-3 font-semibold text-[var(--navy)] disabled:opacity-40"
          >
            It&apos;s clear
          </button>
        </div>
      )}
      <button
        type="button"
        onClick={onDismiss}
        className="mt-2 w-full rounded-lg py-1.5 text-xs text-[var(--muted)] hover:bg-[var(--snow)]"
      >
        Don&apos;t ask about this sidewalk
      </button>
    </div>
  );
}
