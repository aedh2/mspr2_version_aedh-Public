# Traitement sur du compte incomplet `user2`

Ne supprimez jamais un utilisateur sans verifier qu'il s'agit bien d'un essai incomplet.

## 1. Identifier le compte

```sql
SELECT
  u.utilisateur_id,
  u.nom_utilisateur,
  u.email,
  u.role,
  u.statut,
  u.onboarding_complete,
  u.cree_le,
  COUNT(DISTINCT mb.mesure_id) AS mesures_biometriques,
  COUNT(DISTINCT ou.objectif_id) AS objectifs,
  COUNT(DISTINCT ms.mesure_sommeil_id) AS mesures_sommeil,
  COUNT(DISTINCT p.plat_id) AS plats,
  COUNT(DISTINCT ja.journal_id) AS journaux,
  COUNT(DISTINCT se.seance_id) AS seances,
  COUNT(DISTINCT pp.photo_id) AS photos
FROM utilisateur u
LEFT JOIN mesure_biometrique mb ON mb.utilisateur_id = u.utilisateur_id
LEFT JOIN objectif_utilisateur ou ON ou.utilisateur_id = u.utilisateur_id
LEFT JOIN mesure_sommeil_sante ms ON ms.utilisateur_id = u.utilisateur_id
LEFT JOIN plat p ON p.utilisateur_id = u.utilisateur_id
LEFT JOIN journal_alimentaire ja ON ja.utilisateur_id = u.utilisateur_id
LEFT JOIN seance_entrainement se ON se.utilisateur_id = u.utilisateur_id
LEFT JOIN progression_photo pp ON pp.utilisateur_id = u.utilisateur_id
WHERE u.nom_utilisateur = 'user2'
GROUP BY u.utilisateur_id;
```

Le compte est un essai incomplet si :

- `role = 'UTILISATEUR'` ;
- `onboarding_complete = 0` ;
- aucune ligne liee n'existe dans les tables metier ci-dessus.

## 2. Suppression sure si et seulement si le compte est vide

Cette requete ne supprime rien si des donnees liees existent.

```sql
START TRANSACTION;

DELETE FROM utilisateur
WHERE nom_utilisateur = 'user2'
  AND role = 'UTILISATEUR'
  AND onboarding_complete = 0
  AND NOT EXISTS (SELECT 1 FROM mesure_biometrique WHERE mesure_biometrique.utilisateur_id = utilisateur.utilisateur_id)
  AND NOT EXISTS (SELECT 1 FROM objectif_utilisateur WHERE objectif_utilisateur.utilisateur_id = utilisateur.utilisateur_id)
  AND NOT EXISTS (SELECT 1 FROM mesure_sommeil_sante WHERE mesure_sommeil_sante.utilisateur_id = utilisateur.utilisateur_id)
  AND NOT EXISTS (SELECT 1 FROM plat WHERE plat.utilisateur_id = utilisateur.utilisateur_id)
  AND NOT EXISTS (SELECT 1 FROM journal_alimentaire WHERE journal_alimentaire.utilisateur_id = utilisateur.utilisateur_id)
  AND NOT EXISTS (SELECT 1 FROM seance_entrainement WHERE seance_entrainement.utilisateur_id = utilisateur.utilisateur_id)
  AND NOT EXISTS (SELECT 1 FROM progression_photo WHERE progression_photo.utilisateur_id = utilisateur.utilisateur_id);

SELECT ROW_COUNT() AS lignes_supprimees;

COMMIT;
```

Si `lignes_supprimees = 0`, ne forcez pas la suppression : le compte n'est pas vide ou ne correspond pas aux criteres de securite.
