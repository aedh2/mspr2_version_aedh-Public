# ETL HealthAI Coach

Ce dossier contient une implémentation ETL prête à adapter pour la base `healthai_coach` sous XAMPP / phpMyAdmin / MariaDB.

## Scripts fournis

- `etl_common.py` : connexion MySQL, helpers, traçabilité ETL, règles qualité, anomalies, rejets.
- `etl_food.py` : import du dataset nutrition, catalogue aliments, journal alimentaire démo, staging, rejets.
- `etl_gym.py` : import du dataset sport, mesures biométriques, séances, enrichissement en exercices, staging, rejets.
- `etl_sleep.py` : import du dataset sommeil/santé, parsing tension artérielle, mesures sommeil, staging, rejets.
- `etl_exercises.py` : import du catalogue ExerciseDB + GIFs + validations bodyParts/equipments/muscles.
- `run_all_etl.py` : exécution de tous les ETL.
- `tests/test_etl_helpers.py` : petits tests unitaires des helpers critiques.

## Installation

```bash
cd healthai_etl
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Variables à ajuster dans `.env`

- `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`
- chemins des datasets CSV / JSON
- éventuellement `FOOD_IMPORT_DATE`, `GYM_SESSION_DATE`, `SLEEP_MEASURE_DATE`

## Exécution

```bash
python etl_exercises.py
python etl_food.py
python etl_gym.py
python etl_sleep.py
```

ou bien

```bash
python run_all_etl.py
```

## Ce que les ETL font

1. créent une `execution_etl`
2. créent un `lot_donnees`
3. stockent le brut dans `enregistrement_brut`
4. normalisent et stockent dans `stg_import`
5. appliquent des règles qualité simples
6. écrivent `anomalie_donnee` et `enregistrement_rejete`
7. chargent les tables métier
8. ferment proprement l'exécution ETL avec les KPI

## KPI calculés

- lignes lues
- lignes valides
- lignes invalides
- taux qualité
- doublons supprimés
- valeurs corrigées
- rejets

## Remarques de modélisation

- Le dataset food n'a pas d'identité utilisateur : le script crée un utilisateur de démonstration configurable (`FOOD_DEMO_USERNAME`).
- Le dataset gym n'a pas d'identité métier stable : le script crée une identité source par ligne (`gym_line_X`) pour garder une traçabilité claire.
- Le dataset sleep utilise `Person ID` comme identifiant externe.
- `SEANCE_EXERCICE` est alimentée par enrichissement démo à partir du catalogue `EXERCICE`.

## Tests

```bash
python -m unittest tests/test_etl_helpers.py
```
