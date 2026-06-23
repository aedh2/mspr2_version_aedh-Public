# MSPR audit - HealthAI Coach

## Architecture actuelle

Application full-stack:

- Frontend: Next.js App Router, TypeScript, React Query, Recharts, Lucide.
- Backend: FastAPI, SQLAlchemy, Pydantic, JWT auth, pagination commune.
- Base: MariaDB.
- ETL: scripts Python dans `healthai_etl`.
- Docker: services `db`, `backend`, `frontend`, `etl`.
- Media: dossier `data` pour datasets, GIF exercices, photos et assets.

## Modules backend existants

Routes:

- `backend/app/modules/auth.py`: login, refresh, reset password.
- `backend/app/modules/me.py`: espace utilisateur, profil, objectifs, biometrie, sommeil, seances, nutrition, analyse plat, coach posture, recommandations.
- `backend/app/modules/dashboards.py`: dashboards user, admin, super-admin.
- `backend/app/modules/admin.py`: admin, utilisateurs, ETL, qualite, catalogues.
- `backend/app/modules/super_admin.py`: monitoring global, organisations, sources.
- `backend/app/modules/exercices_extra.py`: catalogue exercices avance.
- `backend/app/modules/resources.py`: CRUD generique.
- `backend/app/modules/exports.py`: exports CSV.

Services:

- `meal_analysis.py`: analyse repas avec Hugging Face si active, fallback local.
- `coach_posture.py` et `coach_posture_logic.py`: feedback posture et historique.
- `recommendations.py`: moteur local de recommandations nutrition/sport.
- `me_metrics.py`, `me_nutrition.py`, `me_sport.py`: KPI utilisateur.
- `admin_dashboard.py`, `admin_etl.py`, `admin_quality.py`, `admin_users.py`: admin.

Schemas:

- Auth, meal analysis, coach posture, recommendations, charts `me`.

## Pages frontend existantes

Auth:

- `/login`
- `/forgot-password`
- `/reset-password`

Utilisateur:

- `/me/dashboard`
- `/me/profile`
- `/me/objectifs`
- `/me/mesures-biometriques`
- `/me/sommeil`
- `/me/seances`
- `/me/seances/[id]`
- `/me/exercices`
- `/me/exercices/[id]`
- `/me/journal-alimentaire`
- `/me/nutrition`
- `/me/nutrition/plats/[id]`
- `/me/aliments`
- `/me/photos`
- `/me/recommandations`
- `/me/analyse-plat`
- `/me/coach-posture`
- `/me/historique` ajoute dans cette etape

Admin:

- `/admin/dashboard`
- `/admin/utilisateurs`
- `/admin/utilisateurs/[id]`
- `/admin/etl/executions`
- `/admin/etl/executions/[id]`
- `/admin/etl/lots`
- `/admin/etl/lots/[id]`
- `/admin/etl/compare`
- `/admin/qualite`
- `/admin/controles-qualite`
- `/admin/aliments`
- `/admin/exercices`
- `/admin/regles-qualite`
- `/admin/exports`

Super admin:

- `/super-admin/dashboard`
- `/super-admin/monitoring`
- `/super-admin/organisations`
- `/super-admin/organisations/[id]`
- `/super-admin/sources`

## Tables SQL / ORM existantes

Tables declarees dans `backend/app/db/models.py`:

- `organisation`
- `source_donnees`
- `regle_qualite`
- `utilisateur`
- `objectif_utilisateur`
- `progression_photo`
- `mesure_biometrique`
- `mesure_sommeil_sante`
- `exercice`
- `seance_entrainement`
- `seance_exercice`
- `coach_posture_session`
- `aliment`
- `plat`
- `journal_alimentaire`
- `execution_etl`
- `lot_donnees`
- `enregistrement_brut`
- `stg_import`
- `controle_qualite_donnee`

## ETL existant

Scripts principaux:

- `etl_users.py`: organisations et utilisateurs de demo.
- `etl_food.py`: aliments, journal alimentaire, staging et qualite.
- `etl_gym.py`: mesures sport, biometrie, seances.
- `etl_sleep.py`: sommeil et sante.
- `etl_exercises.py`: catalogue exercices ExerciseDB et GIFs.
- `etl_progression_photos.py`: photos de progression.
- `post_etl_enrichment.py`: enrichissements apres import.
- `run_all_etl.py`: orchestration.

Tables ETL alimentees:

- `execution_etl`
- `lot_donnees`
- `enregistrement_brut`
- `stg_import`
- `controle_qualite_donnee`

Tables metier alimentees:

- `utilisateur`
- `organisation`
- `aliment`
- `journal_alimentaire`
- `exercice`
- `seance_entrainement`
- `seance_exercice`
- `mesure_biometrique`
- `mesure_sommeil_sante`
- `progression_photo`

## NoSQL

Aucune base NoSQL detectee:

- pas de service MongoDB, Redis, Cassandra ou equivalent dans `docker-compose.yml`;
- pas de module backend NoSQL identifie.

## Recommandations actuelles

Un moteur local existe:

- `backend/app/services/recommendations.py`
- schemas dans `backend/app/schemas/recommendations.py`
- endpoint `POST /api/me/recommandations`
- tests `backend/tests/test_recommendation_rules.py`

Il prend en compte profil, objectifs, allergies, regime, budget, niveau sportif, equipement, contraintes sante, preferences et donnees catalogue/ETL. Il renvoie nutrition, sport, scores, justifications et messages de fallback local.

## Appels IA/API actuels

Analyse repas:

- service: `backend/app/services/meal_analysis.py`
- endpoint: `POST /api/me/analyse-plat`
- API: Hugging Face Inference via token env.
- fallback: mock/local si IA desactivee, token absent ou erreur.

Coach posture:

- frontend: MediaPipe `@mediapipe/tasks-vision` dans le navigateur.
- backend: DeepSeek optionnel pour enrichir le feedback texte.
- fallback: feedback local.
- endpoints: `/api/me/coach-posture/feedback`, `/api/me/coach-posture/validate`, `/api/me/coach-posture/history`.

Recommandations:

- moteur local a ce stade; pas d'appel IA externe automatique.

Les cles sont passees par variables d'environnement: `HF_TOKEN`, `HUGGINGFACE_API_TOKEN`, `DEEPSEEK_API_KEY`. Aucun hardcode ajoute.

## Fonctionnalites deja pretes

- Authentification JWT + refresh.
- Espace utilisateur et pages principales.
- Dashboard utilisateur de base, enrichi dans cette etape.
- Admin et super-admin.
- ETL avec tracabilite et controles qualite.
- Analyse repas avec IA externe optionnelle.
- Coach posture avec detection navigateur et historique.
- Recommandations locales nutrition/sport.
- Tests backend critiques et tests ETL.

## Fonctionnalites a corriger ou renforcer

- Docker init SQL: chemin du dump a corriger.
- Dashboard backend: exposer directement macros, proteines, streak, score global et historique consolide.
- Historique: idealement creer un endpoint backend unique plutot qu'une aggregation frontend.
- IA recommandations: documenter clairement le mode local et ajouter option IA externe/fallback si requis MSPR.
- Tests frontend: couvrir dashboard, historique et recommandations UI.
- Encodage docs existantes: plusieurs fichiers affichent des caracteres mal encodes.
