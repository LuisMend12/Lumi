"use client";

type Props = {
  hasEnd: boolean;
  editing: "start" | "end" | null;
  onEdit: (target: "start" | "end" | null) => void;
  onNewRoute: () => void;
};

// Changing a finished route is always a deliberate choice, never a stray map tap (#66).
export default function RouteControls({ hasEnd, editing, onEdit, onNewRoute }: Props) {
  const base =
    "rounded-full border-2 px-3 py-1.5 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--navy)]";
  const idle = `${base} border-[var(--frost)] text-[var(--navy)] hover:border-[var(--navy)]`;
  const active = `${base} border-[var(--navy)] bg-[var(--navy)] text-white`;

  const toggle = (target: "start" | "end") => onEdit(editing === target ? null : target);

  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label="Route controls">
      {hasEnd && (
        <>
          <button type="button" aria-pressed={editing === "start"} className={editing === "start" ? active : idle} onClick={() => toggle("start")}>
            Change start
          </button>
          <button type="button" aria-pressed={editing === "end"} className={editing === "end" ? active : idle} onClick={() => toggle("end")}>
            Change end
          </button>
        </>
      )}
      <button type="button" className={idle} onClick={onNewRoute}>
        New route
      </button>
    </div>
  );
}
