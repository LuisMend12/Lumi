import type { Route, RouteMode, RouteOutcome } from "./api";
import { hazardLabel, MODE_STYLES, walkingMinutes } from "./modes";

export type RouteInsight = {
  comparison: string | null; // how this route trades time against reports, compared with the others
  onRoute: string[]; // reports this route still passes, each labeled with how sure we are
};

type Outcomes = Partial<Record<RouteMode, RouteOutcome>>;

function routeOf(outcome: RouteOutcome | undefined): Route | null {
  return outcome?.status === "ok" ? outcome.route : null;
}

function spots(count: number): string {
  return `${count} reported ${count === 1 ? "spot" : "spots"}`;
}

function extraTime(minutes: number, noExtra: string): string {
  return minutes > 0 ? ` for ${minutes} min more` : noExtra;
}

// On Shortest: point at the first other mode that passes fewer reports.
function shortestComparison(outcomes: Outcomes, shortest: Route): string | null {
  for (const mode of ["safer", "accessible"] as const) {
    const other = routeOf(outcomes[mode]);
    if (!other || other.hazards.length >= shortest.hazards.length) continue;
    const fewer = shortest.hazards.length - other.hazards.length;
    const cost = walkingMinutes(other.distance_m) - walkingMinutes(shortest.distance_m);
    return `${MODE_STYLES[mode].label} passes ${fewer} fewer ${fewer === 1 ? "report" : "reports"}${extraTime(cost, "")}.`;
  }
  return null;
}

// What the chosen route skips or still passes, in plain words. It never says "safe":
// reports can be missing or out of date.
export function routeInsight(outcomes: Outcomes, selected: RouteMode): RouteInsight | null {
  const route = routeOf(outcomes[selected]);
  if (!route) return null;
  const onRoute = route.hazards.map(hazardLabel);
  const shortest = routeOf(outcomes.shortest);
  if (!shortest) return { comparison: null, onRoute };
  if (selected === "shortest") return { comparison: shortestComparison(outcomes, shortest), onRoute };

  const extra = walkingMinutes(route.distance_m) - walkingMinutes(shortest.distance_m);
  const avoided = shortest.hazards.length - route.hazards.length;
  if (avoided > 0) {
    return { comparison: `Skips ${spots(avoided)} on Shortest${extraTime(extra, " at no extra time")}.`, onRoute };
  }
  if (extra > 0) return { comparison: `${extra} min longer than Shortest.`, onRoute };
  return { comparison: "Same walk as Shortest right now.", onRoute };
}
