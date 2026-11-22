"use client";

import { SignInButton, SignedIn, SignedOut, UserButton, useAuth, useClerk } from "@clerk/nextjs";
import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";
import ConditionsBanner from "@/components/ConditionsBanner";
import DemoPanel from "@/components/DemoPanel";
import HowItWorks from "@/components/HowItWorks";
import LumiMark from "@/components/LumiMark";
import MapLegend from "@/components/MapLegend";
import NearbyPrompt from "@/components/NearbyPrompt";
import ReportCrawl from "@/components/ReportCrawl";
import ReportSheet from "@/components/ReportSheet";
import RouteControls from "@/components/RouteControls";
import RouteInsightPanel from "@/components/RouteInsightPanel";
import RoutePicker, { MAP_POINT, MY_LOCATION } from "@/components/RoutePicker";
import { fetchRoute, ROUTE_MODES, USE_MOCKS, type LatLon, type RouteMode, type RouteOutcome } from "@/lib/api";
import { isDemoMode } from "@/lib/demo-api";
import { LANDMARKS } from "@/lib/landmarks";
import { getLocation } from "@/lib/device";
import { createRequestTracker } from "@/lib/latest";
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
// Remembers "Got it" on the How Lumi works panel, per browser.
const HOW_IT_WORKS_KEY = "lumi.howItWorks.dismissed";

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
  // With a route on screen, From/To collapse into one A → B row until the visitor edits (#68).
  const [isEditingRoute, setIsEditingRoute] = useState(false);
  const [reportsUpdatedAt, setReportsUpdatedAt] = useState<Date | null>(null);
  // Hidden until the browser's choice is read, so it never flashes for returning visitors.
  const [isHowItWorksOpen, setIsHowItWorksOpen] = useState(false);

  useEffect(() => {
    try {
      setIsHowItWorksOpen(window.localStorage.getItem(HOW_IT_WORKS_KEY) !== "1");
    } catch {
      setIsHowItWorksOpen(true); // storage blocked (private mode): show it each visit
    }
  }, []);

  function closeHowItWorks() {
    setIsHowItWorksOpen(false);
    try {
      window.localStorage.setItem(HOW_IT_WORKS_KEY, "1");
    } catch {
      // storage blocked: it's closed for this visit only
    }
  }
  // A My location lookup can take seconds. Any newer start (another choice, a map tap,
  // New route) wins, so a late GPS result or error can't override it (#67).
  const [startChoice] = useState(createRequestTracker);

  // Reports to draw on the map, loaded once on open.
  useEffect(() => {
    let isActive = true;
    fetchReports().then((result) => {
      if (!isActive || !result.ok) return;
      setReports(result.data);
      setReportsUpdatedAt(new Date());
    });
    return () => {
      isActive = false;
    };
  }, []);

  // ?from=<landmark id>&to=<landmark id> opens straight onto that route: shareable links,
  // the demo route, and route-state screenshots (#68).
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const from = LANDMARKS.find((landmark) => landmark.id === params.get("from"));
    const to = LANDMARKS.find((landmark) => landmark.id === params.get("to"));
    if (!from || !to) return;
    setFromChoice(from.id);
    setToChoice(to.id);
    void applyPointsRef.current(from.point, to.point);
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
    if (result.ok && reportsRequest === reportsRequestRef.current) {
      setReports(result.data);
      setReportsUpdatedAt(new Date());
    }
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
    if (nextStart && nextEnd) setIsEditingRoute(false);
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
      supersedeStartChoice();
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
      supersedeStartChoice();
      setFromChoice(MAP_POINT);
      await applyPoints(point, currentEnd);
    } else if (editing === "end") {
      setToChoice(MAP_POINT);
      await applyPoints(current, point);
    }
  }

  // A picker choice becomes a point: a landmark, or My location (read only on this tap).
  async function pointForChoice(choice: string, isCurrent: () => boolean = () => true): Promise<LatLon | null> {
    if (choice === MY_LOCATION) {
      setIsLocating(true);
      try {
        const location = await getLocation();
        setIsNearbyOn(true); // the visitor just shared their location (#65)
        return location;
      } finally {
        if (isCurrent()) setIsLocating(false);
      }
    }
    return LANDMARKS.find((landmark) => landmark.id === choice)?.point ?? null;
  }

  // Any lookup for the start still in flight is now stale.
  function supersedeStartChoice() {
    startChoice.cancel();
    setIsLocating(false);
  }

  async function handleFromChange(choice: string) {
    const previous = fromChoice;
    setIsLocating(false);
    const isCurrent = startChoice.begin();
    setFromChoice(choice);
    try {
      const point = await pointForChoice(choice, isCurrent);
      if (!isCurrent()) return; // a newer start was picked while we waited for the location
      await applyPoints(point, pointsRef.current.end);
    } catch (error: unknown) {
      if (!isCurrent()) return;
      setFromChoice(previous);
      setPickerError(error instanceof Error ? error.message : "Couldn't get your location.");
    }
  }

  async function handleToChange(choice: string) {
    setToChoice(choice);
    await applyPoints(pointsRef.current.start, await pointForChoice(choice));
  }

  const applyPointsRef = useRef(applyPoints);
  useEffect(() => {
    applyPointsRef.current = applyPoints;
  });

  function startNewRoute() {
    supersedeStartChoice();
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
  const hasRoute = Boolean(start && end);

  return (
    <main className="flex h-dvh flex-col md:flex-row">
      <section className={`order-2 flex max-h-[58dvh] flex-col gap-4 overflow-y-auto bg-white p-4 shadow-[0_-8px_24px_rgba(16,42,67,0.12)] md:order-1 md:max-h-none md:w-96 md:p-6 md:shadow-[8px_0_24px_rgba(16,42,67,0.08)]`}>
        <header className="flex items-start justify-between gap-3">
          <div>
            <h1 className="font-display flex items-center gap-2.5 text-[40px] leading-none font-extrabold tracking-[-0.01em] text-[var(--navy)]">
              <LumiMark size={36} />
              Lumi
            </h1>
            {/* On phones the tagline gives its space to the chyrons. */}
            <p className="mt-1 hidden text-sm text-[var(--storm)] md:block">
              Winter walking routes around BU, shaped by what people report.
            </p>
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
          <p className="flex items-center gap-2 rounded-lg border border-[var(--frost)] bg-white px-3 py-2 text-sm text-[var(--navy)]">
            <SimulatedBadge />
            Mock data: routes and reports here are not real.
          </p>
        )}

        <ConditionsBanner />

        {isHowItWorksOpen && !hasRoute && <HowItWorks onDismiss={closeHowItWorks} />}

        {hasRoute && !isEditingRoute ? (
          <RouteSummary
            from={choiceLabel(fromChoice)}
            to={choiceLabel(toChoice)}
            onEdit={() => setIsEditingRoute(true)}
          />
        ) : (
          <>
            <RoutePicker
              from={fromChoice}
              to={toChoice}
              isLocating={isLocating}
              onFromChange={handleFromChange}
              onToChange={handleToChange}
            />
            {hint && <p className="rounded-lg bg-[var(--ice)] px-3 py-2 text-sm text-[var(--navy)]">{hint}</p>}
            {(start || end) && (
              <RouteControls
                hasEnd={Boolean(start && end)}
                editing={editing}
                onEdit={setEditing}
                onNewRoute={startNewRoute}
              />
            )}
            {hasRoute && (
              <button
                type="button"
                onClick={() => setIsEditingRoute(false)}
                className="self-start text-sm font-semibold text-[var(--storm)] underline underline-offset-2"
              >
                Done editing
              </button>
            )}
          </>
        )}
        {pickerError && (
          <p role="alert" className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900">
            {pickerError}
          </p>
        )}
        {isLoading && <p className="text-sm text-[var(--storm)]">Finding routes…</p>}
        {sharedError && !isLoading && (
          <p role="alert" className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900">
            {sharedError} Pick different points to try again.
          </p>
        )}

        {/* Chyrons right after the route, before anything else, so they're in view on a phone (#68).
            Before a route exists they stand by with their definitions, so Safer is always defined. */}
        {!sharedError && (
          <ul className="flex flex-col gap-2" aria-label="Route modes">
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
        {hasRoute && !sharedError && !isLoading && <RouteInsightPanel outcomes={outcomes} selectedMode={selectedMode} />}

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

        <MapLegend />

        {isDemo && <DemoPanel route={selectedRoute} onChanged={() => refreshAfterChange()} />}

        <footer className="mt-auto flex flex-col gap-1.5">
          {!isHowItWorksOpen && (
            <button
              type="button"
              onClick={() => setIsHowItWorksOpen(true)}
              className="self-start text-sm font-semibold text-[var(--storm)] underline underline-offset-2"
            >
              How Lumi works
            </button>
          )}
          <p className="text-xs text-[var(--muted)]">
            Routes use community reports, which can be missing or out of date. Lumi never guarantees a route is safe.
          </p>
        </footer>
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
        <div className="font-display pointer-events-none absolute top-4 left-4 z-[800] flex h-8 items-stretch overflow-hidden rounded-md bg-white text-[13px] font-bold tracking-[0.06em] uppercase shadow-[0_4px_14px_rgba(11,37,69,0.12)]">
          <span className="flex items-center bg-[var(--navy)] px-2.5 tracking-[0.12em] text-white">Live</span>
          <span className="flex items-center px-3 text-[var(--storm)]">
            Sidewalk reports · {reports.length}
            {reportsUpdatedAt && (
              <span className="ml-2 text-[var(--navy)]">
                Updated {reportsUpdatedAt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
              </span>
            )}
          </span>
        </div>
        <ReportCrawl reports={reports} />
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
            id="report-button"
            className="font-display absolute right-4 bottom-14 z-[900] rounded-lg bg-[var(--navy)] px-5 py-3 text-lg font-bold tracking-[0.04em] text-white uppercase shadow-[0_6px_18px_rgba(11,37,69,0.35)] hover:bg-[var(--storm)] focus-visible:outline-[var(--sky)] focus-visible:outline-offset-[-5px]"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden className="mr-2 inline-block align-[-3px]">
              <circle cx="9" cy="9" r="7.5" fill="none" stroke="currentColor" strokeWidth="2" />
              <path d="M9 5v5M9 12.6v.4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
            Report blocked sidewalk
          </button>
        )}
      </div>
    </main>
  );
}

// The crawl's own SIMULATED treatment, reused wherever demo data is labeled (#68).
function SimulatedBadge() {
  return (
    <span className="font-display shrink-0 rounded-sm bg-[var(--navy)] px-1.5 py-0.5 text-[12px] font-bold tracking-[0.1em] text-white">
      SIMULATED
    </span>
  );
}

function choiceLabel(choice: string): string {
  if (choice === MY_LOCATION) return "My location";
  if (choice === MAP_POINT) return "Point on the map";
  return LANDMARKS.find((landmark) => landmark.id === choice)?.name ?? "Point on the map";
}

type RouteSummaryProps = { from: string; to: string; onEdit: () => void };

// With a route on screen, From/To fold into one A → B row so the chyrons stay in view (#68).
function RouteSummary({ from, to, onEdit }: RouteSummaryProps) {
  return (
    <div className="flex items-center gap-3">
      <p className="min-w-0 flex-1 text-sm leading-relaxed font-semibold text-[var(--navy)]">
        <span className="whitespace-nowrap">
          <span className="lumi-pin lumi-pin--start mr-1 scale-75 align-middle" aria-hidden>A</span>
          {from}
        </span>
        <span aria-hidden className="mx-1.5 text-[var(--storm)]">→</span>
        <span className="whitespace-nowrap">
          <span className="lumi-pin lumi-pin--end mr-1 scale-75 align-middle" aria-hidden>B</span>
          {to}
        </span>
        <span className="sr-only">{`Route from ${from} to ${to}`}</span>
      </p>
      {/* Change start, Change end and New route live in edit mode, so this row stays one line. */}
      <button type="button" onClick={onEdit} className="shrink-0 text-sm font-semibold text-[var(--storm)] underline underline-offset-2">
        Edit route
      </button>
    </div>
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

function LineSwatch({
  color,
  dashArray,
  casing,
}: {
  color: string;
  dashArray?: string;
  casing: { color: string; opacity: number };
}) {
  return (
    <svg width="28" height="10" aria-hidden className="shrink-0">
      <line x1="2" y1="5" x2="26" y2="5" stroke={casing.color} strokeOpacity={casing.opacity} strokeWidth="9" strokeLinecap="round" />
      <line x1="2" y1="5" x2="26" y2="5" stroke={color} strokeWidth="5" strokeLinecap="round" strokeDasharray={dashArray} />
    </svg>
  );
}

// A lower-third chyron per mode. The chosen one floods with its mode's colour
// and sets its walking minutes at poster scale (#68).
function ModeCard({ mode, outcome, isSelected, onSelect }: ModeCardProps) {
  const style = MODE_STYLES[mode];
  const route = outcome?.status === "ok" ? outcome.route : null;
  const minutes = route ? walkingMinutes(route.distance_m) : null;
  const metres = route ? `${Math.round(route.distance_m).toLocaleString()} m` : null;
  const errorText = outcome?.status === "error" ? outcome.message : null;

  if (isSelected) {
    return (
      <li>
        <button
          type="button"
          onClick={onSelect}
          aria-pressed
          className="grid w-full grid-cols-[1fr_auto] gap-x-3 gap-y-1 rounded-lg px-4 py-3 text-left"
          style={{ background: style.color, color: style.ink }}
        >
          <span className="font-display flex items-center gap-2 text-[19px] leading-none font-bold tracking-[0.05em] uppercase">
            {style.label}
            <span className="rounded-sm border border-current/50 px-1.5 py-0.5 text-[11px] tracking-[0.12em]">Selected</span>
          </span>
          <span className="font-display self-center text-base font-semibold">{metres}</span>
          {minutes !== null && (
            <span className="font-display flex items-baseline gap-1.5 text-[64px] leading-[0.86] font-extrabold tracking-[-0.02em]">
              {minutes}
              <span className="text-xl font-bold tracking-[0.08em] uppercase opacity-80">min</span>
            </span>
          )}
          <span className="max-w-[11rem] self-end text-[13px] leading-snug">
            {errorText ?? MODE_SUMMARIES[mode]}
            {mode === "accessible" && <span className="mt-1 block font-semibold">{ACCESSIBLE_LIMITATION}</span>}
          </span>
        </button>
      </li>
    );
  }

  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={false}
        className="grid w-full grid-cols-[auto_1fr_auto] items-center gap-x-3 rounded-lg border border-[var(--frost)] bg-white px-3 py-2.5 text-left transition-colors hover:border-[var(--storm)]"
      >
        <LineSwatch color={style.color} dashArray={style.dashArray} casing={style.casing} />
        <span className="font-display text-[19px] leading-none font-bold tracking-[0.05em] text-[var(--navy)] uppercase">{style.label}</span>
        <span className="font-display text-base font-semibold text-[var(--navy)]">
          {errorText ? "" : `${minutes ?? "–"} min`}
          {metres && <span className="ml-2 text-[var(--storm)]">{metres}</span>}
        </span>
        <span className="col-span-2 col-start-2 mt-1 text-[13px] leading-snug text-[var(--storm)]">
          {errorText ?? MODE_SUMMARIES[mode]}
          {mode === "accessible" && <span className="mt-0.5 block font-semibold text-[var(--navy)]">{ACCESSIBLE_LIMITATION}</span>}
        </span>
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
