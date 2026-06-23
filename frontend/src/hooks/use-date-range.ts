import { useCallback, useState } from "react";

export type DateRange = { from: string; to: string };

export function useDateRange(initial: DateRange = { from: "", to: "" }) {
  const [range, setRange] = useState<DateRange>(initial);
  const reset = useCallback(() => setRange({ from: "", to: "" }), []);
  const setFrom = useCallback((from: string) => setRange((prev) => ({ ...prev, from })), []);
  const setTo = useCallback((to: string) => setRange((prev) => ({ ...prev, to })), []);
  return { range, setRange, setFrom, setTo, reset };
}
