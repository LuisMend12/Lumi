"use client";

import { useEffect, useRef, useState } from "react";
import type { Verification } from "@/lib/api";
import type { Report } from "@/lib/reports-api";

// What each verification state says in the crawl. Never stated as more certain than it is.
const CRAWL_TEXT: Record<Verification, string> = {
  confirmed: "Sidewalk blocked · Confirmed",
  unverified: "Possible blockage · Unverified report",
  pending: "Photo report · Under review",
};

// Verification as a mark in a fixed cell: filled, hollow, dotted (#68).
function Mark({ verification }: { verification: Verification }) {
  const ring =
    verification === "confirmed"
      ? { fill: "#8ecae6", stroke: "#8ecae6", dash: undefined }
      : verification === "unverified"
        ? { fill: "none", stroke: "#ffb703", dash: undefined }
        : { fill: "none", stroke: "#ffffff", dash: "1 3" };
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden className="shrink-0">
      <circle cx="7" cy="7" r="5" fill={ring.fill} stroke={ring.stroke} strokeWidth="2" strokeDasharray={ring.dash} strokeLinecap="round" />
    </svg>
  );
}

function timeOf(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function Items({ reports }: { reports: Report[] }) {
  return (
    <>
      {reports.map((report, index) => (
        <span key={report.report_id} className="flex items-center gap-2 pr-6">
          {index > 0 && (
            <span aria-hidden className="pr-4 opacity-40">
              ·
            </span>
          )}
          <Mark verification={report.verification} />
          {report.simulated && <span className="rounded-sm bg-white/15 px-1.5 text-[12px] tracking-wider">SIMULATED</span>}
          <span>{CRAWL_TEXT[report.verification]}</span>
          <span className="text-[var(--sky)]">{timeOf(report.reported_at)}</span>
        </span>
      ))}
    </>
  );
}

type Props = { reports: Report[] };

// The signature move: sidewalk reports crawl along the map's bottom edge like a
// storm-coverage ticker (#68). It only moves when the reports are wider than the
// strip, so a short list sits still instead of looping duplicates. Hover or the
// Pause button stops it (WCAG 2.2.2: moving content needs a way to pause it, and
// phones have no hover); reduced motion holds it still and lets the strip scroll by hand.
export default function ReportCrawl({ reports }: Props) {
  const stripRef = useRef<HTMLDivElement>(null);
  const firstCopyRef = useRef<HTMLDivElement>(null);
  const [isOverflowing, setIsOverflowing] = useState(false);
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    const strip = stripRef.current;
    const firstCopy = firstCopyRef.current;
    if (!strip || !firstCopy) return;
    const measure = () => setIsOverflowing(firstCopy.scrollWidth > strip.clientWidth);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(strip);
    observer.observe(firstCopy);
    return () => observer.disconnect();
  }, [reports]);

  return (
    <section
      aria-label="Live sidewalk reports"
      className="font-display absolute inset-x-0 bottom-0 z-[800] flex h-10 items-stretch overflow-hidden bg-[var(--navy)] text-[15px] font-semibold tracking-wide text-white"
    >
      <span className="flex shrink-0 items-center bg-[var(--sky)] px-3 text-[15px] font-extrabold tracking-[0.14em] text-[var(--navy)]">
        LIVE
      </span>
      {isOverflowing && (
        <button
          type="button"
          onClick={() => setIsPaused((paused) => !paused)}
          aria-pressed={isPaused}
          aria-label={isPaused ? "Play the report crawl" : "Pause the report crawl"}
          title={isPaused ? "Play" : "Pause"}
          className="flex w-10 shrink-0 items-center justify-center border-r border-white/15 text-white hover:bg-[var(--storm)] focus-visible:outline-[var(--sky)] focus-visible:outline-offset-[-3px]"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden>
            {isPaused ? (
              <path d="M3.5 2v10l8.5-5z" fill="currentColor" />
            ) : (
              <path d="M3.5 2h2.5v10H3.5zM8 2h2.5v10H8z" fill="currentColor" />
            )}
          </svg>
        </button>
      )}
      {reports.length === 0 ? (
        <p className="flex items-center px-4">No sidewalk reports right now.</p>
      ) : (
        <div
          ref={stripRef}
          className="lumi-crawl-strip min-w-0 flex-1 overflow-hidden focus-visible:outline-[var(--sky)] focus-visible:outline-offset-[-3px]"
          tabIndex={isOverflowing ? 0 : undefined}
          aria-label={isOverflowing ? "Report list. Focus pauses it; with reduced motion, scroll with the arrow keys." : undefined}
        >
          <div
            className={`flex h-full w-max items-center whitespace-nowrap ${isOverflowing ? "lumi-crawl" : ""}`}
            style={isPaused ? { animationPlayState: "paused" } : undefined}
          >
            <div ref={firstCopyRef} className="flex items-center pl-4">
              <Items reports={reports} />
            </div>
            {/* The second copy makes the loop seamless; screen readers hear the list once. */}
            {isOverflowing && (
              <div aria-hidden className="flex items-center pl-4">
                <Items reports={reports} />
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
