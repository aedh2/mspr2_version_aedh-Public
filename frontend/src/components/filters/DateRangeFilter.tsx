"use client";

import { Button } from "@/src/components/ui/button";
import { Field, Input } from "@/src/components/ui/forms";

export type DateRangeValue = { from: string; to: string };

export function DateRangeFilter({
  value,
  onChange,
  labelFrom = "Du",
  labelTo = "Au"
}: {
  value: DateRangeValue;
  onChange: (next: DateRangeValue) => void;
  labelFrom?: string;
  labelTo?: string;
}) {
  return (
    <div className="filter-bar" style={{ alignItems: "flex-end", gap: 12 }}>
      <Field label={labelFrom}>
        <Input
          type="date"
          value={value.from}
          onChange={(event) => onChange({ ...value, from: event.target.value })}
        />
      </Field>
      <Field label={labelTo}>
        <Input
          type="date"
          value={value.to}
          onChange={(event) => onChange({ ...value, to: event.target.value })}
        />
      </Field>
      <Button
        type="button"
        variant="secondary"
        onClick={() => onChange({ from: "", to: "" })}
        disabled={!value.from && !value.to}
      >
        Reinitialiser
      </Button>
    </div>
  );
}
