// Tracks which of several overlapping async requests is the newest, so a slow
// older one (e.g. a My location lookup) can't overwrite a newer choice (#67).
export interface RequestTracker {
  // Start a request. The returned check stays true until the next begin() or cancel().
  begin(): () => boolean;
  // Make every request in flight stale, e.g. when the visitor picks something else.
  cancel(): void;
}

export function createRequestTracker(): RequestTracker {
  let latest = 0;
  return {
    begin() {
      const id = ++latest;
      return () => id === latest;
    },
    cancel() {
      latest += 1;
    },
  };
}
