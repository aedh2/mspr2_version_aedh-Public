import { AlertCircle, Database, Loader2 } from "lucide-react";
import { Button } from "@/src/components/ui/button";

export function LoadingState({ label = "Chargement des donnees..." }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <Loader2 className="spin" size={18} />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message?: string; onRetry?: () => void }) {
  return (
    <div className="state state-error" role="alert">
      <AlertCircle size={18} />
      <span>{message || "Impossible de charger les donnees."}</span>
      {onRetry ? <Button variant="secondary" onClick={onRetry}>Reessayer</Button> : null}
    </div>
  );
}

export function EmptyState({ label = "Aucune donnee disponible." }: { label?: string }) {
  return (
    <div className="state">
      <Database size={18} />
      <span>{label}</span>
    </div>
  );
}

export function SkeletonLoader({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton-loader" aria-label="Chargement">
      {Array.from({ length: rows }).map((_, index) => (
        <span className="skeleton skeleton-line" key={index} />
      ))}
    </div>
  );
}
