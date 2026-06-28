# Checklist Soutenance HealthAI

## URLs

- Frontend : http://localhost:3000
- Healthcheck : http://localhost:8000/health (montre l'état des **deux bases** : relationnel + documentaire)
- Swagger : http://localhost:8000/api/docs
- OpenAPI : http://localhost:8000/api/openapi.json

## Démo SQL + NoSQL (à montrer au jury)

1. `curl http://localhost:8000/health` → `"databases":{"relationnel":"mariadb","documentaire":"ok"}`.
2. Générer une recommandation et une analyse de plat depuis le front (espace utilisateur).
3. Relire la couche NoSQL via Swagger ou curl :
   - `GET /api/ai/recommandations/history` (collection `recommendations`)
   - `GET /api/ai/analyse-repas/history` (collection `food_analyses`)
   - `GET /api/ai/ai-calls/history` (collection `ai_provider_calls` — observabilité IA)
   - `GET /api/ai/recommandations/feedback/history` (collection `recommendation_feedback`)
4. Voir les documents bruts dans MongoDB :
   ```powershell
   docker exec healthai-mongo mongosh healthai_nosql --quiet --eval "db.getCollectionNames()"
   docker exec healthai-mongo mongosh healthai_nosql --quiet --eval "db.recommendations.findOne()"
   ```
5. **Résilience** : si Mongo est coupé (`docker compose stop mongo`), l'API reste fonctionnelle et `/health` bascule `documentaire` sur `unavailable` (mode dégradé, aucune écriture bloquante).

## Comptes

- Utilisateur : `user` / `user`
- Admin : `admin` / `admin`
- Super-admin : `superadmin` / `superadmin`

## Parcours utilisateur

1. Connexion avec `user/user`.
2. Ouvrir le dashboard : vérifier poids, IMC, sommeil, calories, séances, objectif actif et dernière photo.
3. Modifier le profil : email, organisation, identifiant, prénom, nom, genre, taille, date de naissance.
4. Ajouter une mesure biométrique et vérifier le refresh de la table.
5. Ajouter une mesure sommeil/santé.
6. Créer une séance, ouvrir son détail, ajouter un exercice.
7. Créer un plat, ouvrir son détail, ajouter une ligne alimentaire.
8. Créer un objectif puis le marquer réussi, échoué ou annulé.
9. Ouvrir les photos de progression et vérifier `photo_url`.
10. Ouvrir le catalogue exercices, filtrer et consulter un détail avec GIF.

## Parcours admin

1. Connexion avec `admin/admin`.
2. Ouvrir le dashboard admin et vérifier les KPI.
3. Créer puis modifier un aliment.
4. Modifier un exercice.
5. Activer/désactiver une règle qualité.
6. Ouvrir les contrôles qualité et les graphiques.
7. Ouvrir les exécutions ETL, lots, détail lot, raw/staging/contrôles.
8. Tester la vue avant/après ETL avec un lot, une entité et une ref externe.

## Parcours super-admin

1. Connexion avec `superadmin/superadmin`.
2. Ouvrir dashboard et monitoring.
3. Vérifier exécutions en échec, lots bloqués, qualité/volumes par source.
4. Créer/modifier une organisation avec image.
5. Modifier, activer/désactiver une source.

## Commandes utiles

```powershell
docker compose -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml ps
docker compose -f docker-compose.yml logs --tail=100 backend
docker compose -f docker-compose.yml logs --tail=100 frontend
```

## Bugs connus

Aucun bug bloquant connu à ce stade. Ne pas réimporter le dump SQL si les tables existent déjà.
