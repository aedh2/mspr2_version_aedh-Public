import type { Role } from "@/src/types/domain";

export type RouteDef = {
  path: string;
  label: string;
  roles?: Role[];
};

export const ROUTE_LABELS: Record<string, string> = {
  "/me": "Espace personnel",
  "/me/dashboard": "Tableau de bord",
  "/me/profile": "Profil",
  "/me/onboarding": "Personnalisation",
  "/me/objectifs": "Objectifs",
  "/me/mesures-biometriques": "Biometrie",
  "/me/sommeil": "Sommeil",
  "/me/seances": "Seances",
  "/me/exercices": "Exercices",
  "/me/nutrition": "Nutrition",
  "/me/nutrition/plats": "Plats",
  "/me/aliments": "Aliments",
  "/me/journal-alimentaire": "Journal alimentaire",
  "/me/historique": "Historique",
  "/me/photos": "Photos",
  "/me/recommandations": "Recommandations",
  "/me/analyse-plat": "Analyse photo repas",
  "/me/coach-posture": "Coach posture",
  "/admin": "Administration",
  "/admin/dashboard": "Tableau de bord",
  "/admin/utilisateurs": "Utilisateurs",
  "/admin/executions-etl": "Executions ETL",
  "/admin/etl": "ETL",
  "/admin/etl/executions": "Executions",
  "/admin/etl/lots": "Lots",
  "/admin/etl/compare": "Avant / apres",
  "/admin/qualite": "Controles qualite",
  "/admin/controles-qualite": "Controles qualite",
  "/admin/aliments": "Aliments",
  "/admin/exercices": "Exercices",
  "/admin/regles-qualite": "Regles qualite",
  "/admin/exports": "Exports",
  "/super-admin": "Super administration",
  "/super-admin/dashboard": "Tableau de bord",
  "/super-admin/organisations": "Organisations",
  "/super-admin/sources": "Sources",
  "/super-admin/monitoring": "Monitoring",
  "/login": "Connexion",
  "/forgot-password": "Mot de passe oublie",
  "/reset-password": "Reinitialiser le mot de passe"
};

export function labelForPath(path: string): string {
  if (ROUTE_LABELS[path]) return ROUTE_LABELS[path];
  // dynamic ids → fall back to last segment
  const last = path.split("/").filter(Boolean).pop() || "";
  return decodeURIComponent(last).replace(/[-_]/g, " ");
}

export function buildBreadcrumbs(pathname: string): { href: string; label: string }[] {
  const segments = pathname.split("/").filter(Boolean);
  const crumbs: { href: string; label: string }[] = [];
  let current = "";
  for (const segment of segments) {
    current += `/${segment}`;
    crumbs.push({ href: current, label: labelForPath(current) });
  }
  return crumbs;
}
