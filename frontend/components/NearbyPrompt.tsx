"use client";

import type { NearbySegment } from "@/lib/reports-api";

type Props = {
  segment: NearbySegment;
  isSending: boolean;
  message: string | null;
  onVote: (blocked: boolean) => void;
  onDismiss: () => void;
};

export default function NearbyPrompt({ segment, isSending, message, onVote, onDismiss }: Props) {
  const question = segment.status === "blocked" ? "Is this sidewalk still blocked?" : "Is this sidewalk blocked?";

  return (
    <div
      role="region"
      aria-label="Nearby sidewalk question"
      className="absolute inset-x-4 top-4 z-[900] rounded-2xl bg-white p-4 shadow-[0_8px_24px_rgba(16,42,67,0.2)] md:inset-x-auto md:right-4 md:w-80"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-semibold text-[var(--navy)]">{question}</p>
        <button type="button" onClick={onDismiss} className="rounded-lg px-2 text-sm text-[var(--muted)] hover:bg-[var(--snow)]">
          Not now
        </button>
      </div>
      <p className="mt-1 text-xs text-[var(--muted)]">The highlighted sidewalk is near you.</p>
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
    </div>
  );
}
