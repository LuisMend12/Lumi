"use client";

import { SignInButton, SignedIn, SignedOut, UserButton, useAuth, useClerk } from "@clerk/nextjs";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import DemoPanel from "@/components/DemoPanel";
import MapLegend from "@/components/MapLegend";
import NearbyPrompt from "@/components/NearbyPrompt";
import ReportSheet from "@/components/ReportSheet";
import RouteControls from "@/components/RouteControls";
import RoutePicker, { MAP_POINT, MY_LOCATION } from "@/components/RoutePicker";
import { fetchRoute, ROUTE_MODES, USE_MOCKS, type LatLon, type RouteMode, type RouteOutcome } from "@/lib/api";
import { isDemoMode } from "@/lib/demo-api";
import { LANDMARKS } from "@/lib/landmarks";
import { getLocation } from "@/lib/device";
import { ACCESSIBLE_LIMITATION, MODE_STYLES, MODE_SUMMARIES, walkingMinutes } from "@/lib/modes";
import { VOTE_OUTCOME_TEXT } from "@/lib/reporting";
import {
  fetchNearby,
  fetchReports,
  voteOnSegment,
  type NearbySegment,
  type Report,
} from "@/lib/reports-api";

const NEARBY_POLL_MS = 60_000;
// Pick up other people's reports and blocks while the page is open (#59).
const REFRESH_MS = 20_000;

// Leaflet touches `window`, so the map only renders in the browser.
const RouteMap = dynamic(() => import("@/components/RouteMap"), {
  ssr: false,
  loading: () => <div className="h-full w-full animate-pulse bg-[var(--ice)]" />,
});

type Outcomes = Partial<Record<RouteMode, RouteOutcome>>;

export default function Home() {
  const { isSignedIn, getToken } = useAuth();
  const { openSignIn } = useClerk();
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
  const [isDemo, setIsDemo] = useState(false);
  // Nearby checks read location, so they start only after the visitor asks (#65).
  const [isNearbyOn, setIsNearbyOn] = useState(false);
  // Which point the next map tap moves once a route exists; taps are ignored otherwise (#66).
  const [editing, setEditing] = useState<"start" | "end" | null>(null);
  // What the From / To pickers show: a landmark id, MY_LOCATION, MAP_POINT, or "" (#67).
  const [fromChoice, setFromChoice] = useState("");
  const [toChoice, setToChoice] = useState("");
  const [isLocating, setIsLocating] = useState(false);
  const [pickerError, setPickerError] = useState<string | null>(null);

  // Reports to draw on the map, loaded once on open.
  useEffect(() => {
    let isActive = true;
    fetchReports().then((result) => isActive && result.ok && setReports(result.data));
    return () => {
      isActive = false;
    };
  }, []);

  // The Demo panel only exists when the backend runs in demo mode (#47).
  useEffect(() => {
    let isActive = true;
    isDemoMode().then((on) => isActive && setIsDemo(on));
    return () => {
      isActive = false;
    };
  }, []);

  // If this browser already allowed location on an earlier visit, nearby checks
  // can start without showing a permission dialog. Otherwise we wait for a tap.
  useEffect(() => {
    let isActive = true;
    navigator.permissions
      ?.query({ name: "geolocation" })
      .then((status) => isActive && status.state === "granted" && setIsNearbyOn(true))
      .catch(() => {}); // the Permissions API is optional; the button still works
    return () => {
      isActive = false;
    };
  }, []);

  // Once on, check every minute for a reported sidewalk nearby to ask about.
  useEffect(() => {
    if (!isNearbyOn) return;
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
  }, [isNearbyOn]);

  // The start and end on screen right now. Async code reads these instead of
  // the values captured when it began, and each route request gets a number:
  // results from an older request are dropped (#54, #59).
  const pointsRef = useRef<{ start: LatLon | null; end: LatLon | null }>({ start: null, end: null });
  const routeRequestRef = useRef(0);
  // The request number of a load the visitor asked for while it runs, else null.
  const explicitLoadRef = useRef<number | null>(null);
  const reportsRequestRef = useRef(0);

  function setPoints(nextStart: LatLon | null, nextEnd: LatLon | null) {
    pointsRef.current = { start: nextStart, end: nextEnd };
    routeRequestRef.current += 1; // any route request in flight is now stale
    setStart(nextStart);
    setEnd(nextEnd);
  }

  async function loadRoutes(from: LatLon, to: LatLon, { quiet = false } = {}) {
    // A background refresh never replaces a load the visitor asked for that's still running.
    if (quiet && explicitLoadRef.current === routeRequestRef.current) return;
    const request = ++routeRequestRef.current;
    if (!quiet) {
      explicitLoadRef.current = request;
      setIsLoading(true);
    }
    const results = await Promise.all(ROUTE_MODES.map((mode) => fetchRoute(from, to, mode)));
    if (request !== routeRequestRef.current) return; // the user picked new points meanwhile
    explicitLoadRef.current = null;
    // A background refresh that couldn't reach the server keeps the routes on screen:
    // a network blip shouldn't wipe a good route. Loads the visitor asked for show the error.
    if (quiet && results.some((outcome) => outcome.status === "error" && outcome.offline)) return;
    setOutcomes(Object.fromEntries(ROUTE_MODES.map((mode, i) => [mode, results[i]])));
    setIsLoading(false);
  }

  // A sidewalk may have changed status: show the new reports and recompute the routes on screen.
  async function refreshAfterChange({ quiet = false } = {}) {
    const reportsRequest = ++reportsRequestRef.current;
    const result = await fetchReports();
    // An older reports response that arrives late doesn't overwrite a newer one.
    if (result.ok && reportsRequest === reportsRequestRef.current) setReports(result.data);
    const { start: from, end: to } = pointsRef.current;
    if (from && to) await loadRoutes(from, to, { quiet });
  }

  // Keep the latest refresh function for the interval below, which is set up once.
  const refreshRef = useRef(refreshAfterChange);
  useEffect(() => {
    refreshRef.current = refreshAfterChange;
  });

  // Other people's reports, votes and demo actions show up within REFRESH_MS,
  // and right away when the tab comes back into view (#59).
  useEffect(() => {
    const refreshIfVisible = () => {
      if (document.visibilityState === "visible") refreshRef.current({ quiet: true });
    };
    const id = setInterval(refreshIfVisible, REFRESH_MS);
    document.addEventListener("visibilitychange", refreshIfVisible);
    return () => {
      clearInterval(id);
      document.removeEventListener("visibilitychange", refreshIfVisible);
    };
  }, []);

  // Set either point from the map, a picker, or My location; routes load once both exist.
  async function applyPoints(nextStart: LatLon | null, nextEnd: LatLon | null) {
    setEditing(null);
    setPickerError(null);
    setPoints(nextStart, nextEnd);
    if (nextStart && nextEnd) {
      await loadRoutes(nextStart, nextEnd);
    } else {
      setOutcomes({});
      setIsLoading(false);
    }
  }

  async function handleMapClick(point: LatLon) {
    const { start: current, end: currentEnd } = pointsRef.current;
    if (!current) {
      setFromChoice(MAP_POINT);
      await applyPoints(point, currentEnd);
      return;
    }
    if (!currentEnd) {
      setToChoice(MAP_POINT);
      await applyPoints(current, point);
      return;
    }
    // A finished route only changes on purpose: Change start / Change end / New route (#66).
    if (editing === "start") {
      setFromChoice(MAP_POINT);
      await applyPoints(point, currentEnd);
    } else if (editing === "end") {
      setToChoice(MAP_POINT);
      await applyPoints(current, point);
    }
  }

  // A picker choice becomes a point: a landmark, or My location (read only on this tap).
  async function pointForChoice(choice: string): Promise<LatLon | null> {
    if (choice === MY_LOCATION) {
      setIsLocating(true);
      try {
        const location = await getLocation();
        setIsNearbyOn(true); // the visitor just shared their location (#65)
        return location;
      } finally {
        setIsLocating(false);
      }
    }
    return LANDMARKS.find((landmark) => landmark.id === choice)?.point ?? null;
  }

  async function handleFromChange(choice: string) {
    const previous = fromChoice;
    setFromChoice(choice);
    try {
      await applyPoints(await pointForChoice(choice), pointsRef.current.end);
    } catch (error: unknown) {
      setFromChoice(previous);
      setPickerError(error instanceof Error ? error.message : "Couldn't get your location.");
    }
  }

  async function handleToChange(choice: string) {
    setToChoice(choice);
    await applyPoints(pointsRef.current.start, await pointForChoice(choice));
  }

  function startNewRoute() {
    setFromChoice("");
    setToChoice("");
    void applyPoints(null, null);
  }

  async function handleVote(blocked: boolean) {
    if (!nearby) return;
    if (!isSignedIn) {
      openSignIn(); // browsing is open; answering needs a real account (4 different people)
      return;
    }
    const segmentId = nearby.segment_id;
    setIsVoting(true);
    try {
      const location = await getLocation();
      const token = await getToken();
      if (!token) {
        openSignIn();
        return;
      }
      const result = await voteOnSegment(token, segmentId, blocked, location);
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
    if (!isSignedIn) {
      openSignIn();
      return;
    }
    setSheetNotice(null);
    setIsSheetOpen(true);
  }

  const promptSegment = isNearbyOn && nearby && nearby.segment_id !== dismissedSegment ? nearby : null;

  const hint = !start
    ? "Pick a start above, or tap the map (A)."
    : !end
      ? "Pick a destination, or tap the map (B)."
      : editing
        ? `Tap the map to move ${editing === "start" ? "the start (A)" : "the destination (B)"}.`
        : null;
  const sharedError = sameErrorForAllModes(outcomes);
  const selectedOutcome = outcomes[selectedMode];
  const selectedRoute = selectedOutcome?.status === "ok" ? selectedOutcome.route : null;

  return (
    <main className="flex h-dvh flex-col md:flex-row">
      <section className="order-2 flex max-h-[45dvh] flex-col gap-4 overflow-y-auto bg-white p-4 shadow-[0_-8px_24px_rgba(16,42,67,0.12)] md:order-1 md:max-h-none md:w-96 md:p-6 md:shadow-[8px_0_24px_rgba(16,42,67,0.08)]">
        <header className="flex items-start justify-between gap-3">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight text-[var(--navy)]">Lumi</h1>
            <p className="text-sm text-[var(--muted)]">Winter walking routes around BU, shaped by what people report.</p>
          </div>
          <SignedOut>
            <SignInButton mode="modal">
              <button
                type="button"
                className="shrink-0 whitespace-nowrap rounded-full border-2 border-[var(--navy)] px-4 py-1.5 text-sm font-semibold text-[var(--navy)] hover:bg-[var(--ice)]"
              >
                Sign in
              </button>
            </SignInButton>
          </SignedOut>
          <SignedIn>
            <UserButton />
          </SignedIn>
        </header>

        {USE_MOCKS && (
          <p className="rounded-lg border-2 border-dashed border-amber-500 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-900">
            Mock data: routes and hazards are simulated, not real reports.
          </p>
        )}
        <RoutePicker
          from={fromChoice}
          to={toChoice}
          isLocating={isLocating}
          onFromChange={handleFromChange}
          onToChange={handleToChange}
        />
        {pickerError && (
          <p role="alert" className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900">
            {pickerError}
          </p>
        )}
        {hint && <p className="rounded-lg bg-[var(--ice)] px-3 py-2 text-sm text-[var(--navy)]">{hint}</p>}
        {(start || end) && (
          <RouteControls
            hasEnd={Boolean(start && end)}
            editing={editing}
            onEdit={setEditing}
            onNewRoute={startNewRoute}
          />
        )}
        <NearbyToggle
          isOn={isNearbyOn}
          notice={locationNotice}
          onChange={(isOn) => {
            setIsNearbyOn(isOn);
            if (!isOn) {
              setLocationNotice(null);
              setNearby(null); // don't flash an old sidewalk question when checks are turned back on
            }
          }}
        />
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

        <MapLegend />

        {isDemo && <DemoPanel route={selectedRoute} onChanged={() => refreshAfterChange()} />}

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
        {isSheetOpen && isSignedIn ? (
          <ReportSheet
            getToken={getToken}
            notice={sheetNotice}
            onClose={() => setIsSheetOpen(false)}
            onReported={() => {
              setIsNearbyOn(true);
              refreshAfterChange();
            }}
          />
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

type NearbyToggleProps = {
  isOn: boolean;
  notice: string | null; // e.g. location blocked
  onChange: (isOn: boolean) => void;
};

// Lumi reads location only after this tap (or a report), never on page load (#65).
function NearbyToggle({ isOn, notice, onChange }: NearbyToggleProps) {
  if (!isOn) {
    return (
      <button
        type="button"
        onClick={() => onChange(true)}
        className="self-start rounded-full border-2 border-[var(--frost)] px-3 py-1.5 text-sm font-medium text-[var(--navy)] hover:border-[var(--navy)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--navy)]"
      >
        Check sidewalks near me
      </button>
    );
  }
  return (
    <p className="flex items-center gap-2 text-sm text-[var(--muted)]">
      <span>{notice ?? "Checking reported sidewalks near you while Lumi is open."}</span>
      <button
        type="button"
        onClick={() => onChange(false)}
        className="shrink-0 rounded-md px-2 py-1 font-medium text-[var(--navy)] underline underline-offset-2 hover:bg-[var(--snow)]"
      >
        Stop
      </button>
    </p>
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
        <span className="mt-1 block text-xs text-[var(--muted)]">{MODE_SUMMARIES[mode]}</span>
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
