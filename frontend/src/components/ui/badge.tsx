export function StatusBadge({ value }: { value?: string | boolean | null }) {
  const label = typeof value === "boolean" ? (value ? "Oui" : "Non") : value || "N/A";
  const normalized = String(label).toLowerCase();
  const tone =
    normalized.includes("actif") || normalized.includes("succes") || normalized.includes("termine")
      ? "success"
      : normalized.includes("erreur") || normalized.includes("bloquant") || normalized.includes("inactif")
        ? "danger"
        : normalized.includes("admin") || normalized.includes("warning")
          ? "warning"
          : "neutral";

  return <span className={`badge badge-${tone}`}>{label}</span>;
}
