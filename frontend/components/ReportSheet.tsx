"use client";

import { useEffect, useState } from "react";
import { getLocation, shrinkPhoto } from "@/lib/device";
import { REPORT_OUTCOME_TEXT } from "@/lib/reporting";
import { submitReport, type ReportResult } from "@/lib/reports-api";

type Props = {
  getToken: () => Promise<string | null>; // Clerk session token; the page asks for sign-in before opening the sheet
  notice: string | null; // e.g. why a photo is required
  onClose: () => void;
  onReported: (result: ReportResult) => void;
};

type Stage = { kind: "editing" } | { kind: "sending" } | { kind: "done"; message: string } | { kind: "error"; message: string };

export default function ReportSheet({ getToken, notice, onClose, onReported }: Props) {
  const [photo, setPhoto] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [stage, setStage] = useState<Stage>({ kind: "editing" });

  // The preview URL holds the photo in memory; release it when it changes or the sheet closes.
  useEffect(() => {
    if (!photo) {
      setPreviewUrl(null); // the picker was cancelled: drop the revoked preview, don't show a broken image (#56)
      return;
    }
    const url = URL.createObjectURL(photo);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  async function handleSubmit() {
    if (!photo) return;
    setStage({ kind: "sending" });
    try {
      const [location, shrunk] = await Promise.all([getLocation(), shrinkPhoto(photo)]);
      const token = await getToken(); // fetched last: Clerk tokens only last about a minute
      if (!token) return setStage({ kind: "error", message: "Please sign in again, then try once more." });
      const result = await submitReport(token, location, shrunk);
      if (!result.ok) return setStage({ kind: "error", message: result.message });
      setStage({ kind: "done", message: REPORT_OUTCOME_TEXT[result.data.outcome] });
      onReported(result.data);
    } catch (error: unknown) {
      setStage({ kind: "error", message: error instanceof Error ? error.message : "Something went wrong." });
    }
  }

  const isSending = stage.kind === "sending";

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="report-title"
      className="absolute inset-x-0 bottom-0 z-[1000] rounded-t-2xl bg-white p-4 shadow-[0_-12px_32px_rgba(16,42,67,0.25)] md:inset-x-auto md:right-4 md:bottom-4 md:w-96 md:rounded-2xl"
    >
      <div className="flex items-start justify-between gap-4">
        <h2 id="report-title" className="text-lg font-semibold text-[var(--navy)]">
          Report a blocked sidewalk
        </h2>
        <button type="button" onClick={onClose} className="rounded-lg px-2 py-1 text-sm text-[var(--muted)] hover:bg-[var(--snow)]">
          Close
        </button>
      </div>

      {notice && <p className="mt-2 rounded-lg bg-[var(--ice)] px-3 py-2 text-sm text-[var(--navy)]">{notice}</p>}

      {stage.kind === "done" ? (
        <p role="status" className="mt-3 rounded-lg bg-[var(--ice)] px-3 py-3 text-sm text-[var(--navy)]">
          {stage.message}
        </p>
      ) : (
        <>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Take a photo of the sidewalk where you are. Lumi uses your current location and checks the photo before it changes any route.
          </p>
          <label className="mt-3 flex cursor-pointer items-center justify-center rounded-xl border-2 border-dashed border-[var(--frost)] bg-[var(--snow)] p-3 text-sm font-medium text-[var(--navy)] hover:border-[var(--navy)]">
            {previewUrl ? (
              // eslint-disable-next-line @next/next/no-img-element -- local blob preview, not an optimizable asset
              <img src={previewUrl} alt="Selected sidewalk photo" className="max-h-40 rounded-lg object-contain" />
            ) : (
              "Take or choose a photo"
            )}
            <input
              type="file"
              accept="image/*"
              capture="environment"
              className="sr-only"
              onChange={(event) => {
                setPhoto(event.target.files?.[0] ?? null);
                setStage({ kind: "editing" });
              }}
            />
          </label>
          {stage.kind === "error" && (
            <p role="alert" className="mt-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-900">
              {stage.message}
            </p>
          )}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!photo || isSending}
            className="mt-3 w-full rounded-xl bg-[var(--navy)] px-4 py-3 font-semibold text-white disabled:opacity-40"
          >
            {isSending ? "Sending…" : "Submit report"}
          </button>
        </>
      )}
    </div>
  );
}
