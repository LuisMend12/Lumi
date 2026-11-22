import { ROUTE_MODES } from "@/lib/api";
import { MODE_STYLES, NAVY, VERIFICATION_STYLES } from "@/lib/modes";

const SWATCH_WIDTH = 32;

function LineSwatch({ color, dashArray }: { color: string; dashArray?: string }) {
  return (
    <svg width={SWATCH_WIDTH} height="10" aria-hidden className="shrink-0">
      <line x1="3" y1="5" x2={SWATCH_WIDTH - 3} y2="5" stroke={color} strokeWidth="4" strokeLinecap="round" strokeDasharray={dashArray} />
    </svg>
  );
}

function DotSwatch({ fill }: { fill: string }) {
  return (
    <svg width={SWATCH_WIDTH} height="16" aria-hidden className="shrink-0">
      <circle cx={SWATCH_WIDTH / 2} cy="8" r="6" fill={fill} stroke={NAVY} strokeWidth="2" />
    </svg>
  );
}

// What the lines and markers on the map mean (#66). Collapsed by default.
export default function MapLegend() {
  return (
    <details className="rounded-xl bg-[var(--snow)] px-3 py-2 text-sm text-[var(--navy)]">
      <summary className="cursor-pointer font-medium">What the map shows</summary>
      <ul className="mt-2 flex flex-col gap-1.5">
        {ROUTE_MODES.map((mode) => (
          <li key={mode} className="flex items-center gap-2">
            <LineSwatch color={MODE_STYLES[mode].color} dashArray={MODE_STYLES[mode].dashArray} />
            {MODE_STYLES[mode].label} route
          </li>
        ))}
        <li className="flex items-center gap-2">
          <span className="lumi-pin lumi-pin--start shrink-0" aria-hidden>A</span>
          <span className="lumi-pin lumi-pin--end shrink-0" aria-hidden>B</span>
          Start and destination
        </li>
        {(["confirmed", "unverified", "pending"] as const).map((verification) => (
          <li key={verification} className="flex items-center gap-2">
            <DotSwatch fill={VERIFICATION_STYLES[verification].fill} />
            {VERIFICATION_STYLES[verification].label} report
          </li>
        ))}
        <li className="flex items-center gap-2">
          <LineSwatch color="#f59e0b" />
          Reported sidewalk near you
        </li>
      </ul>
    </details>
  );
}
