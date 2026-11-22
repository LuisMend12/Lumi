const STEPS = [
  { title: "Pick A and B", text: "Choose a BU landmark or your location, or tap the map." },
  { title: "Compare three walks", text: "Shortest, Safer and Accessible, each with its time and what it skips." },
  { title: "Report a blocked sidewalk", text: "Snap a photo. Lumi checks it, then routes around it." },
  { title: "Neighbors keep it current", text: "People nearby answer with one tap: still blocked, or clear now." },
];

type Props = { onDismiss: () => void };

// A short first-visit explainer. It sits in the panel, never over the map, and stays dismissed.
export default function HowItWorks({ onDismiss }: Props) {
  return (
    <section aria-labelledby="how-it-works" className="shrink-0 rounded-lg border-2 border-[var(--frost)] bg-white p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 id="how-it-works" className="font-display text-[17px] font-bold tracking-[0.06em] text-[var(--navy)] uppercase">
          How Lumi works
        </h2>
        <button
          type="button"
          onClick={onDismiss}
          className="rounded-md px-2 py-1 text-sm font-semibold text-[var(--storm)] underline underline-offset-2 hover:bg-[var(--snow)]"
        >
          Got it
        </button>
      </div>
      <ol className="mt-2 flex flex-col gap-2">
        {STEPS.map((step, index) => (
          <li key={step.title} className="grid grid-cols-[auto_1fr] gap-x-2.5">
            <span
              aria-hidden
              className="font-display flex h-6 w-6 items-center justify-center rounded-full bg-[var(--navy)] text-[13px] font-bold text-white"
            >
              {index + 1}
            </span>
            <p className="text-sm leading-snug text-[var(--navy)]">
              <span className="font-semibold">{step.title}.</span> {step.text}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
