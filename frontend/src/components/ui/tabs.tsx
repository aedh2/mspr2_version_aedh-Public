"use client";

export type TabItem<T extends string> = {
  value: T;
  label: string;
  disabled?: boolean;
};

export function Tabs<T extends string>({
  items,
  value,
  onChange,
  label
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (value: T) => void;
  label: string;
}) {
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          className="tab-button"
          role="tab"
          aria-selected={value === item.value}
          disabled={item.disabled}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
