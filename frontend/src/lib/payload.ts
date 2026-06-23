/**
 * Helper pour nettoyer et normaliser les payloads API
 * Gère :
 * - Suppression des champs undefined
 * - Conversion "" → null pour les champs optionnels
 * - Conversion des nombres en string → number
 * - Conversion des booléens
 * - Suppression des dates vides
 * - Suppression des champs read-only (id, *_id, cree_le, modifie_le, *_url, gif_*_path, image_path)
 */

export interface CleanPayloadOptions {
  /** Champs à exclure du payload (en plus des defaults) */
  exclude?: string[];
  /** Champs numériques à convertir */
  numericFields?: string[];
  /** Champs booléens à convertir */
  booleanFields?: string[];
  /** Champs de date (ISO string) */
  dateFields?: string[];
  /** Champs requis a conserver meme s'ils ressemblent a des champs read-only */
  requiredFields?: string[];
  /** Si true, convertir "" en null pour tous les champs optionnels */
  emptyStringToNull?: boolean;
}

const DEFAULT_READONLY_FIELDS = [
  // IDs
  'id',
  'aliment_id',
  'exercice_id',
  'organisation_id',
  'utilisateur_id',
  'source_id',
  'seance_id',
  'photo_id',
  'objectif_id',
  'mesure_id',
  'mesure_sommeil_id',
  'plat_id',
  'journal_id',
  'regle_id',
  'lot_id',
  'execution_id',
  'seance_exercice_id',
  'controle_id',
  'enregistrement_id',
  'stg_id',
  // Timestamps
  'cree_le',
  'modifie_le',
  // URLs (computed)
  'image_url',
  'gif_180_url',
  'gif_360_url',
  'gif_720_url',
  'gif_1080_url',
  'photo_url',
  // Paths (stored as-is, not sent back)
  'image_path',
  'gif_180_path',
  'gif_360_path',
  'gif_720_path',
  'gif_1080_path',
];

export function cleanPayload<T extends Record<string, unknown>>(
  values: T,
  options: CleanPayloadOptions = {}
): Partial<T> {
  const {
    exclude = [],
    numericFields = [],
    booleanFields = [],
    dateFields = [],
    requiredFields = [],
    emptyStringToNull = true,
  } = options;

  const fieldsToExclude = new Set([...DEFAULT_READONLY_FIELDS, ...exclude]);
  requiredFields.forEach((field) => fieldsToExclude.delete(field));
  const result: Partial<T> = {};

  for (const [key, value] of Object.entries(values)) {
    // Exclure les champs read-only
    if (fieldsToExclude.has(key)) {
      continue;
    }

    // Ignorer undefined
    if (value === undefined) {
      continue;
    }

    // Convertir "" en null si option activée
    if (emptyStringToNull && value === '') {
      result[key as keyof T] = null as unknown as T[keyof T];
      continue;
    }

    // Ignorer les chaînes vides (sauf si on veut les convertir en null)
    if (!emptyStringToNull && value === '') {
      continue;
    }

    // Convertir les nombres en string → number
    if (numericFields.includes(key) && typeof value === 'string') {
      const num = parseFloat(value);
      result[key as keyof T] = (Number.isFinite(num) ? num : null) as unknown as T[keyof T];
      continue;
    }

    // Convertir les booléens en string → boolean
    if (booleanFields.includes(key) && typeof value === 'string') {
      result[key as keyof T] = (value.toLowerCase() === 'true' || value === '1') as unknown as T[keyof T];
      continue;
    }

    // Traiter les dates : si vide, mettre null
    if (dateFields.includes(key)) {
      if (value === '' || !value) {
        result[key as keyof T] = null as unknown as T[keyof T];
      } else {
        result[key as keyof T] = value as T[keyof T];
      }
      continue;
    }

    // Copier la valeur telle quelle
    result[key as keyof T] = value as T[keyof T];
  }

  return result;
}

/**
 * Présets pour les types courants
 */

export const ALIMENT_FIELDS: CleanPayloadOptions = {
  numericFields: [
    'calories_kcal',
    'proteines_g',
    'glucides_g',
    'lipides_g',
    'fibres_g',
    'sucres_g',
    'sodium_mg',
    'cholesterol_mg',
  ],
};

export const EXERCICE_FIELDS: CleanPayloadOptions = {
  requiredFields: [
    'source_id',
    'external_id',
    'gif_180_path',
    'gif_360_path',
    'gif_720_path',
    'gif_1080_path',
  ],
};

export const UTILISATEUR_FIELDS: CleanPayloadOptions = {
  numericFields: ['taille_cm', 'organisation_id'],
  dateFields: ['date_naissance'],
  requiredFields: ['organisation_id'],
};

export const MESURE_BIOMETRIQUE_FIELDS: CleanPayloadOptions = {
  numericFields: [
    'poids_kg',
    'taille_cm',
    'imc',
    'taux_masse_grasse',
    'bpm_repos',
    'bpm_moyen',
    'bpm_max',
    'eau_l',
  ],
  dateFields: ['mesure_le'],
};

export const MESURE_SOMMEIL_FIELDS: CleanPayloadOptions = {
  numericFields: [
    'duree_sommeil_h',
    'qualite_sommeil_score',
    'activite_physique_min_jour',
    'stress_score',
    'frequence_cardiaque_bpm',
    'tension_systolique',
    'tension_diastolique',
    'pas_jour',
  ],
  dateFields: ['mesure_le'],
};

export const SEANCE_FIELDS: CleanPayloadOptions = {
  numericFields: [
    'duree_seance_min',
    'calories_brulees_total',
    'frequence_entrainement_j_sem',
    'eau_l',
  ],
  dateFields: ['date_seance'],
};

export const SEANCE_EXERCICE_FIELDS: CleanPayloadOptions = {
  numericFields: [
    'exercice_id',
    'ordre_exercice',
    'series_nb',
    'repetitions_nb',
    'charge_kg',
    'duree_min',
    'calories_brulees_estimees',
  ],
  requiredFields: ['exercice_id'],
};

export const PLAT_FIELDS: CleanPayloadOptions = {
  numericFields: ['calories_totales_kcal'],
  dateFields: ['consomme_le'],
};

export const JOURNAL_ALIMENTAIRE_FIELDS: CleanPayloadOptions = {
  numericFields: ['aliment_id', 'quantite', 'calories_kcal', 'eau_ml'],
  dateFields: ['consomme_le'],
  requiredFields: ['aliment_id'],
};

export const OBJECTIF_FIELDS: CleanPayloadOptions = {
  dateFields: ['date_debut', 'date_fin'],
};

export const PROGRESSION_PHOTO_FIELDS: CleanPayloadOptions = {
  dateFields: ['prise_le'],
  requiredFields: ['objectif_id', 'image_path'],
};

export const SOURCE_DONNEES_FIELDS: CleanPayloadOptions = {
  booleanFields: ['actif'],
};

export const REGLE_QUALITE_FIELDS: CleanPayloadOptions = {
  booleanFields: ['actif'],
};

export const ORGANISATION_FIELDS: CleanPayloadOptions = {
  requiredFields: ['image_path'],
};
