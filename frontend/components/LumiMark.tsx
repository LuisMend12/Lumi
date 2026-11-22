// The Lumi mark, the same shapes as app/icon.svg: a walk curving up to its destination.
export default function LumiMark({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <rect width="32" height="32" rx="7" fill="#0b2545" />
      <path d="M8 25 C 8 16, 20 20, 20 11" fill="none" stroke="#8ecae6" strokeWidth="4" strokeLinecap="round" />
      <circle cx="22.5" cy="8.5" r="4" fill="#ffffff" />
    </svg>
  );
}
