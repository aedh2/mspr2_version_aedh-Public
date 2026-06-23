"use client";

import { Activity, DatabaseZap, Download, Dumbbell, Moon, Salad, ShieldCheck, Soup, Users } from "lucide-react";
import { Button } from "@/src/components/ui/button";
import { useExport, type ExportDataset } from "@/src/hooks/use-export";
import { Page } from "./_shared";

const DATASETS: { key: ExportDataset; label: string; description: string; icon: any }[] = [
  { key: "utilisateurs", label: "Utilisateurs", description: "Comptes, roles, organisations", icon: Users },
  { key: "biometrie", label: "Biometrie", description: "Mesures biometriques", icon: Activity },
  { key: "sommeil", label: "Sommeil & sante", description: "Sommeil, stress, activite", icon: Moon },
  { key: "sport", label: "Sport", description: "Seances + exercices realises", icon: Dumbbell },
  { key: "nutrition", label: "Journal alimentaire", description: "Lignes du journal", icon: Salad },
  { key: "plats", label: "Plats", description: "Plats consommes", icon: Soup },
  { key: "qualite", label: "Controles qualite", description: "Controles & decisions", icon: ShieldCheck },
  { key: "executions", label: "Executions ETL", description: "Historique executions", icon: DatabaseZap },
  { key: "lots", label: "Lots ETL", description: "Lots de donnees", icon: DatabaseZap }
];

export function ExportsPage() {
  const exporter = useExport();
  const pendingDataset = exporter.isPending ? (exporter.variables as ExportDataset | undefined) : undefined;

  return (
    <Page title="Exports" eyebrow="Administration">
      <p className="muted">
        Format CSV (UTF-8). Le telechargement demarre automatiquement.
      </p>
      <div className="export-grid">
        {DATASETS.map((dataset) => {
          const busy = pendingDataset === dataset.key;
          const Icon = dataset.icon;
          return (
            <article key={dataset.key} className="export-card">
              <div className="export-card-header">
                <div className="export-icon">
                  <Icon size={20} />
                </div>
                <div>
                  <h3>{dataset.label}</h3>
                  <p>{dataset.description}</p>
                </div>
              </div>
              <Button onClick={() => exporter.mutate(dataset.key)} disabled={exporter.isPending}>
                <Download size={16} />
                {busy ? "En cours..." : "Telecharger CSV"}
              </Button>
            </article>
          );
        })}
      </div>
      {exporter.isError ? <div className="form-error">{exporter.error.message}</div> : null}
    </Page>
  );
}
