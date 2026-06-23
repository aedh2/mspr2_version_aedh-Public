export const genreOptions = [
  { value: "Inconnu", label: "Inconnu" },
  { value: "Homme", label: "Homme" },
  { value: "Femme", label: "Femme" },
  { value: "Autre", label: "Autre" }
] as const;

export const objectiveOptions = [
  { value: "PERTE_POIDS", label: "Perte de poids" },
  { value: "MAINTIEN_FORME", label: "Maintien" },
  { value: "GAIN_MUSCLE", label: "Prise de masse" },
  { value: "EQUILIBRE_VIE", label: "Sante" },
  { value: "SOMMEIL", label: "Sommeil" },
  { value: "AUTRE", label: "Autre" }
] as const;

export const activityOptions = [
  { value: "sedentaire", label: "Sedentaire" },
  { value: "leger", label: "Leger" },
  { value: "modere", label: "Modere" },
  { value: "actif", label: "Actif" },
  { value: "tres_actif", label: "Tres actif" }
] as const;

export const sportLevelOptions = [
  { value: "debutant", label: "Debutant" },
  { value: "intermediaire", label: "Intermediaire" },
  { value: "avance", label: "Avance" }
] as const;

export const budgetOptions = [
  { value: "", label: "Non precise" },
  { value: "faible", label: "Faible" },
  { value: "moyen", label: "Moyen" },
  { value: "eleve", label: "Eleve" }
] as const;

export function splitList(value?: string | null) {
  return (value || "")
    .replace(/\n/g, ",")
    .split(/[,;]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function joinList(value?: string[] | null) {
  return (value || []).filter(Boolean).join(", ");
}

export function numberOrNull(value: string | number | null | undefined) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}
