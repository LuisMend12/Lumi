import { ROUTE_MODES } from "@/lib/api";
import { AMBER, MODE_STYLES, NAVY, VERIFICATION_STYLES } from "@/lib/modes";

const SWATCH_WIDTH = 32;

function LineSwatch({
  color,
  dashArray,
  casing = "#ffffff",
  casingOpacity = 1,
}: {
  color: string;
  dashArray?: string;
  casing?: string;
  casingOpacity?: number;
}) {
  return (
    <svg width={SWATCH_WIDTH} height="10" aria-hidden className="shrink-0">
      <line x1="3" y1="5" x2={SWATCH_WIDTH - 3} y2="5" stroke={casing} strokeOpacity={casingOpacity} strokeWidth="8" strokeLinecap="round" />
      <line x1="3" y1="5" x2={SWATCH_WIDTH - 3} y2="5" stroke={color} strokeWidth="4" strokeLinecap="round" strokeDasharray={dashArray} />
    </svg>
  );
}

function DotSwatch({ fill, stroke, dashArray }: { fill: string; stroke: string; dashArray?: string }) {
  // Confirmed marks are white-ringed navy, so give them a navy halo to read on the light legend.
  return (
    <svg width={SWATCH_WIDTH} height="16" aria-hidden className="shrink-0">
      <circle cx={SWATCH_WIDTH / 2} cy="8" r="6" fill={fill} stroke={stroke === "#ffffff" ? NAVY : stroke} strokeWidth="2.5" strokeDasharray={dashArray} strokeLinecap="round" />
    </svg>
  );
}

// What the lines and markers on the map mean (#66). Collapsed by default.
export default function MapLegend() {
  return (
    <details className="rounded-xl bg-[var(--snow)] px-3 py-2 text-sm text-[var(--navy)]">
      <summary className="font-display cursor-pointer text-[15px] font-bold tracking-[0.04em] uppercase">What the map shows</summary>
      <ul className="mt-2 flex flex-col gap-1.5">
        {ROUTE_MODES.map((mode) => (
          <li key={mode} className="flex items-center gap-2">
            <LineSwatch
              color={MODE_STYLES[mode].color}
              dashArray={MODE_STYLES[mode].dashArray}
              casing={MODE_STYLES[mode].casing.color}
              casingOpacity={MODE_STYLES[mode].casing.opacity}
            />
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
            <DotSwatch {...VERIFICATION_STYLES[verification]} />
            {VERIFICATION_STYLES[verification].label} report
          </li>
        ))}
        <li className="flex items-center gap-2">
          <LineSwatch color={AMBER} />
          Reported sidewalk near you
        </li>
      </ul>
    </details>
  );
}
