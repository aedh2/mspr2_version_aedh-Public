# MSPR implementation plan - HealthAI Coach

## 1. Stabilisation workspace

- Garder toutes les modifications dans `C:\mspr2_try`.
- Corriger le chemin SQL Docker.
- Nettoyer les artefacts temporaires avant livraison.
- Verifier `python -m compileall backend\app`, tests backend et build frontend.

## 2. Application web utilisateur

- Conserver auth et sidebar.
- Stabiliser `/me/dashboard`, `/me/profile`, `/me/objectifs`, `/me/nutrition`, `/me/exercices`, `/me/recommandations`, `/me/historique`.
- Harmoniser les empty states, loading states, erreurs et focus visible.
- Ajouter tests frontend sur routes critiques.

## 3. Dashboard KPI

- Creer un endpoint backend dedie, par exemple `GET /api/me/dashboard/kpis`.
- Calculer cote backend: readiness, nutrition, activite, sommeil, regularite, streak, calories moyennes, repas/jour.
- Exposer macros et proteines si les donnees existent.
- Garder fallbacks explicites si une source manque.

## 4. Moteur recommandations nutrition/sport

- Garder `RecommendationEngine`.
- Ajouter ou verifier contraintes critiques: allergies, regime, budget, equipement, contraintes sante.
- Exposer un endpoint clair et documente.
- Ajouter tests unitaires sur incompatibilites allergie/equipement/securite.

## 5. Appels IA externes et fallback

- Documenter Hugging Face, DeepSeek et MediaPipe.
- Ajouter un service d'orchestration IA si les recommandations doivent appeler une API externe.
- Garder fallback local obligatoire.
- Ne jamais exposer ni logger les cles.
- Ajouter timeouts, erreurs lisibles et indicateur `fallback_utilise`.

## 6. ETL et donnees

- Documenter exactement les datasets sources.
- Verifier les tables alimentees par chaque script.
- Ajouter des controles qualite ciblant nutrition, sport et sommeil.
- Exposer une vue admin claire des derniers imports et erreurs.

## 7. Admin et monitoring IA

- Ajouter KPI IA/API: nombre d'appels, provider, taux d'echec, fallback, latence.
- Ajouter page admin monitoring IA.
- Relier les erreurs IA aux logs sans secret.

## 8. Coach posture conserve et integre

- Ne pas casser MediaPipe.
- Conserver fallback simulation.
- Garder validation et historique.
- Ajouter lien dashboard/historique vers coach posture.
- Documenter limites non medicales.

## 9. Historique utilisateur

- Remplacer l'aggregation frontend par un endpoint backend unique.
- Inclure repas, seances, objectifs, sommeil, biometrie, coach posture, analyse repas.
- Ajouter filtres type/date/source.

## 10. Tests

- Backend: recommandations, auth, IA fallback, dashboard KPI.
- ETL: mapping datasets et controles qualite.
- Frontend: dashboard, historique, recommandations, auth guard.
- Accessibilite: focus, boutons, erreurs, navigation clavier.

## 11. Documentation

- Mettre a jour README.
- Garder `AI_SETUP.md`.
- Ajouter page MSPR: IA/API utilisees, variables env, fallbacks, limites.
- Ajouter contrats API principaux.

## 12. Docker final

- Corriger le volume SQL.
- Verifier `.env.example`.
- Lancer build final seulement quand les changements sont stabilises.
- Documenter commandes de lancement et comptes de test.

## Fichiers prioritaires a modifier ensuite

- `docker-compose.yml`
- `backend/app/modules/dashboards.py`
- `backend/app/services/me_metrics.py`
- `backend/app/services/recommendations.py`
- `backend/app/schemas/recommendations.py`
- `backend/app/modules/me.py`
- `frontend/src/features/me/pages/MeDashboard.tsx`
- `frontend/src/features/me/pages/Historique.tsx`
- `frontend/src/features/me/pages/Recommandations.tsx`
- `frontend/app/styles.css`
- `README.md`
- `AI_SETUP.md`
