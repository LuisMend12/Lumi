"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import NearbyPrompt from "@/components/NearbyPrompt";
import ReportSheet from "@/components/ReportSheet";
import { fetchRoute, ROUTE_MODES, USE_MOCKS, type LatLon, type RouteMode, type RouteOutcome } from "@/lib/api";
import { getLocation } from "@/lib/device";
import { ACCESSIBLE_LIMITATION, MODE_STYLES, walkingMinutes } from "@/lib/modes";
import { VOTE_OUTCOME_TEXT } from "@/lib/reporting";
import {
  fetchNearby,
  fetchReports,
  voteOnSegment,
  type NearbySegment,
  type Report,
} from "@/lib/reports-api";

const NEARBY_POLL_MS = 60_000;

// Leaflet touches `window`, so the map only renders in the browser.
const RouteMap = dynamic(() => import("@/components/RouteMap"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-[var(--ice)]" />,
});

type Outcomes = Partial<Record<RouteMode, RouteOutcome>>;

export default function Home() {
  const [start, setStart] = useState<LatLon | null>(null);
  const [end, setEnd] = useState<LatLon | null>(null);
  const [outcomes, setOutcomes] = useState<Outcomes>({});
  const [selectedMode, setSelectedMode] = useState<RouteMode>("safer");
  const [isLoading, setIsLoading] = useState(false);
  const [reports, setReports] = useState<Report[]>([]);
  const [nearby, setNearby] = useState<NearbySegment | null>(null);
  const [dismissedSegment, setDismissedSegment] = useState<string | null>(null);
  const [voteMessages, setVoteMessages] = useState<Record<string, string>>({});
  const [isVoting, setIsVoting] = useState(false);
  const [sheetNotice, setSheetNotice] = useState<string | null>(null);
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [locationNotice, setLocationNotice] = useState<string | null>(null);

  // Reports to draw on the map, loaded once on open.
  useEffect(() => {
    let isActive = true;
    fetchReports().then((result) => isActive && result.ok && setReports(result.data));
    return () => {
      isActive = false;
    };
  }, []);

  // While the app is open, check every minute for a reported sidewalk nearby to ask about.
  useEffect(() => {
    let isActive = true;
    async function checkNearby() {
      try {
        const result = await fetchNearby(await getLocation());
        if (!isActive) return;
        setLocationNotice(null);
        if (result.ok) setNearby(result.data[0] ?? null);
      } catch (error: unknown) {
        if (isActive) setLocationNotice(error instanceof Error ? error.message : "Location unavailable.");
      }
    }
    checkNearby();
    const id = setInterval(checkNearby, NEARBY_POLL_MS);
    return () => {
      isActive = false;
      clearInterval(id);
    };
  }, []);

  async function loadRoutes(from: LatLon, to: LatLon) {
    setIsLoading(true);
    const results = await Promise.all(ROUTE_MODES.map((mode) => fetchRoute(from, to, mode)));
    setOutcomes(Object.fromEntries(ROUTE_MODES.map((mode, i) => [mode, results[i]])));
    setIsLoading(false);
  }

  // A sidewalk changed status: show the new reports and recompute any routes on screen.
  async function refreshAfterChange() {
    const result = await fetchReports();
    if (result.ok) setReports(result.data);
    if (start && end) await loadRoutes(start, end);
  }

  async function handleMapClick(point: LatLon) {
    if (!start || end) {
      setStart(point);
      setEnd(null);
      setOutcomes({});
      return;
    }
    setEnd(point);
    await loadRoutes(start, point);
  }

  async function handleVote(blocked: boolean) {
    if (!nearby) return;
    const segmentId = nearby.segment_id;
    setIsVoting(true);
    try {
      const result = await voteOnSegment(segmentId, blocked, await getLocation());
      if (!result.ok) {
        setVoteMessages((messages) => ({ ...messages, [segmentId]: result.message }));
      } else if (result.data.outcome === "photo_required") {
        setSheetNotice(VOTE_OUTCOME_TEXT.photo_required);
        setIsSheetOpen(true);
      } else {
        setVoteMessages((messages) => ({ ...messages, [segmentId]: VOTE_OUTCOME_TEXT[result.data.outcome] }));
        if (result.data.outcome === "status_changed") await refreshAfterChange();
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Something went wrong.";
      setVoteMessages((messages) => ({ ...messages, [segmentId]: message }));
    } finally {
      setIsVoting(false);
    }
  }

  function openReportSheet() {
    setSheetNotice(null);
    setIsSheetOpen(true);
  }

  const promptSegment = nearby && nearby.segment_id !== dismissedSegment ? nearby : null;

  const hint = !start ? "Tap the map to set your start." : !end ? "Now tap your destination." : null;
  const sharedError = sameErrorForAllModes(outcomes);

  return (
    <main className="flex h-dvh flex-col md:flex-row">
      <section className="order-2 flex max-h-[45dvh] flex-col gap-4 overflow-y-auto bg-white p-4 shadow-[0_-8px_24px_rgba(16,42,67,0.12)] md:order-1 md:max-h-none md:w-96 md:p-6 md:shadow-[8px_0_24px_rgba(16,42,67,0.08)]">
        <header>
          <h1 className="text-3xl font-semibold tracking-tight text-[var(--navy)]">Lumi</h1>
          <p className="text-sm text-[var(--muted)]">Smarter paths. Safer winters.</p>
        </header>

        {USE_MOCKS && (
          <p className="rounded-lg border-2 border-dashed border-amber-500 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900">
            Mock data: routes and hazards are simulated, not real reports.
          </p>
        )}
        {hint && <p className="rounded-lg bg-[var(--ice)] px-3 py-2 text-sm text-[var(--navy)]">{hint}</p>}
        {locationNotice && <p className="text-xs text-[var(--muted)]">{locationNotice}</p>}
        {isLoading && <p className="text-sm text-[var(--muted)]">Finding routes…</p>}

        {sharedError && !isLoading && (
          <p role="alert" className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900">
            {sharedError} Tap the map to start again.
          </p>
        )}

        {end && !isLoading && !sharedError && (
          <ul className="flex flex-col gap-2">
            {ROUTE_MODES.map((mode) => (
              <ModeCard
                key={mode}
                mode={mode}
                outcome={outcomes[mode]}
                isSelected={mode === selectedMode}
                onSelect={() => setSelectedMode(mode)}
              />
            ))}
          </ul>
        )}

        <p className="mt-auto text-xs text-[var(--muted)]">
          Routes use community reports, which can be missing or out of date. Lumi never guarantees a route is safe.
        </p>
      </section>

      <div className="relative order-1 flex-1 md:order-2">
        <RouteMap
          start={start}
          end={end}
          outcomes={outcomes}
          selectedMode={selectedMode}
          reports={reports}
          nearbySegment={promptSegment}
          onMapClick={handleMapClick}
          onSelectRoute={setSelectedMode}
        />
        {promptSegment && (
          <NearbyPrompt
            segment={promptSegment}
            isSending={isVoting}
            message={voteMessages[promptSegment.segment_id] ?? null}
            onVote={handleVote}
            onDismiss={() => setDismissedSegment(promptSegment.segment_id)}
          />
        )}
        {isSheetOpen ? (
          <ReportSheet notice={sheetNotice} onClose={() => setIsSheetOpen(false)} onReported={refreshAfterChange} />
        ) : (
          <button
            type="button"
            onClick={openReportSheet}
            className="absolute right-4 bottom-4 z-[900] rounded-full bg-[var(--navy)] px-5 py-3 font-semibold text-white shadow-[0_8px_24px_rgba(16,42,67,0.35)] hover:bg-[#1d3d5c] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--navy)]"
          >
            Report blocked sidewalk
          </button>
        )}
      </div>
    </main>
  );
}

type ModeCardProps = {
  mode: RouteMode;
  outcome: RouteOutcome | undefined;
  isSelected: boolean;
  onSelect: () => void;
};

function ModeCard({ mode, outcome, isSelected, onSelect }: ModeCardProps) {
  const style = MODE_STYLES[mode];
  const summary =
    outcome?.status === "ok"
      ? `${walkingMinutes(outcome.route.distance_m)} min · ${Math.round(outcome.route.distance_m)} m`
      : (outcome?.message ?? "");

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={isSelected}
        className={`w-full rounded-xl border-2 p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-[var(--navy)] ${
          isSelected ? "border-[var(--navy)] bg-[var(--ice)]" : "border-transparent bg-[var(--snow)] hover:border-[var(--frost)]"
        }`}
      >
        <span className="flex items-center gap-2">
          <span className="h-1.5 w-6 rounded-full" style={{ background: style.color }} aria-hidden />
          <span className="font-semibold text-[var(--navy)]">{style.label}</span>
          <span className="ml-auto text-sm text-[var(--muted)]">{summary}</span>
        </span>
        {mode === "accessible" && (
          <span className="mt-1 block text-xs font-medium text-amber-800">{ACCESSIBLE_LIMITATION}</span>
        )}
        {isSelected && outcome?.status === "ok" && (
          <span className="mt-2 block text-sm leading-snug text-[var(--navy)]">{outcome.route.mode_description}</span>
        )}
      </button>
    </li>
  );
}

// e.g. "too close" or "outside coverage": the same for every mode, so show it once.
function sameErrorForAllModes(outcomes: Outcomes): string | null {
  const results = ROUTE_MODES.map((mode) => outcomes[mode]);
  if (results.some((outcome) => outcome?.status !== "error")) return null;
  const messages = new Set(results.map((outcome) => (outcome?.status === "error" ? outcome.message : "")));
  return messages.size === 1 ? [...messages][0] : null;
}
