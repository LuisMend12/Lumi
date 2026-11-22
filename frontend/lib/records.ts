// A copy of `record` without `key`; the original is left untouched.
export function withoutKey<T>(record: Readonly<Record<string, T>>, key: string): Record<string, T> {
  if (!(key in record)) return { ...record };
  return Object.fromEntries(Object.entries(record).filter(([entryKey]) => entryKey !== key));
}
