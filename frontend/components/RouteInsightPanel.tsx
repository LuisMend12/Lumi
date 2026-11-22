import type { RouteMode, RouteOutcome } from "@/lib/api";
import { routeInsight } from "@/lib/route-insight";

type Props = { outcomes: Partial<Record<RouteMode, RouteOutcome>>; selectedMode: RouteMode };

const MAX_LISTED = 3;

// Why this route: what it skips compared with Shortest, and what it still passes.
export default function RouteInsightPanel({ outcomes, selectedMode }: Props) {
  const insight = routeInsight(outcomes, selectedMode);
  if (!insight) return null;
  const count = insight.onRoute.length;
  const spacing = insight.comparison ? "mt-1" : "";

  return (
    <section
      aria-label="About this route"
      className="shrink-0 rounded-lg border-l-4 border-[var(--storm)] bg-[var(--ice)] px-3 py-2.5 text-sm text-[var(--navy)]"
    >
      {insight.comparison && <p className="font-semibold">{insight.comparison}</p>}
      {count === 0 ? (
        <p className={spacing}>No reports on this route right now. Conditions change fast, so watch your step.</p>
      ) : (
        <>
          <p className={spacing}>
            Still passes {count} reported {count === 1 ? "spot" : "spots"}:
          </p>
          <ul className="mt-1 list-disc pl-5">
            {insight.onRoute.slice(0, MAX_LISTED).map((label, index) => (
              <li key={`${label}-${index}`}>{label}</li>
            ))}
            {count > MAX_LISTED && <li>and {count - MAX_LISTED} more</li>}
          </ul>
        </>
      )}
    </section>
  );
}
