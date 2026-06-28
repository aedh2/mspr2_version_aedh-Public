# HealthAI Coaching — MSPR

Plateforme complète de coaching santé : pipeline ETL Python, API FastAPI, front Next.js, persistance polyglotte MariaDB (relationnel) + MongoDB (documentaire).

## Stack

| Couche | Techno |
|---|---|
| Base relationnelle (SQL) | MariaDB 10.11 |
| Base documentaire (NoSQL) | MongoDB 7 |
| Backend API | FastAPI (Python 3.11) + SQLAlchemy + PyMongo |
| Frontend | Next.js 14 (App Router, TypeScript) |
| ETL | Python (pandas, SQLAlchemy) |
| Conteneurs | Docker / docker-compose |

### Persistance polyglotte

- **MariaDB** — données structurées et relationnelles : profils, mesures biométriques/sommeil, séances, catalogue exercices/aliments, objectifs, traçabilité ETL.
- **MongoDB** — documents à schéma variable produits par l'IA : analyses de plats (`food_analyses`) et recommandations générées (`recommendations`). La couche NoSQL est **tolérante aux pannes** : si MongoDB est indisponible, l'API reste fonctionnelle (mode dégradé, aucune écriture bloquante).

## Arborescence

```
backend/         API FastAPI (auth, CRUD, dashboards, ETL admin)
frontend/        Next.js (espace utilisateur, admin, super-admin)
healthai_etl/    Pipeline ETL (CSV/JSON → MariaDB)
data/            Datasets sources + GIFs exercices + photos
exports/         Exports CSV générés
docker-compose.yml
```

---

## Lancement via Docker (recommandé)

### Prérequis
- Docker Desktop ou Docker Engine + Docker Compose v2

### Démarrage

```bash
# 1. Cloner le repo
git clone https://github.com/hichembenamara/mspr-fiiinale.git
cd mspr-fiiinale

# 2. Copier le fichier d'env (les valeurs par défaut suffisent)
cp .env.example .env

# 3. Démarrer la base + backend + frontend
docker compose up -d --build

# 4. (Optionnel) Lancer le pipeline ETL pour seeder la BDD
docker compose --profile etl run --rm etl
```

### Accès

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/api |
| Swagger | http://localhost:8000/api/docs |
| Healthcheck | http://localhost:8000/health |
| MariaDB | localhost:3306 |
| MongoDB | localhost:27017 |

> Le `/health` renvoie l'état des deux bases : `{"databases":{"relationnel":"mariadb","documentaire":"ok"}}`.

### Identifiants de test

Après ETL, des utilisateurs sont créés. Voir `healthai_etl/exports/generated_users_credentials.csv` pour les comptes (admins, super-admins, utilisateurs lambda).

### Commandes utiles

```bash
docker compose ps                       # État des services
docker compose logs -f backend          # Logs API
docker compose logs -f frontend         # Logs front
docker compose down                     # Arrêter
docker compose down -v                  # Arrêter + supprimer la BDD
docker compose up -d --build backend    # Rebuild d'un service
```

---

## Lancement en local (sans Docker)

### Prérequis
- Python 3.11+
- Node.js 20+
- MariaDB ou MySQL 8 disponible localement (port 3306)

### 1. Base de données

```bash
mysql -uroot -p < "backend/healthai_coaching bdd remplite.sql"
```

### 2. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows
pip install -r requirements.txt

# Variables d'env (cf. backend/.env.example)
export DB_HOST=127.0.0.1
export DB_USER=root
export DB_PASSWORD=
export DB_NAME=healthai_coaching
export JWT_SECRET_KEY=dev-secret
export MEDIA_ROOT=../data
export MEDIA_BASE_URL=http://localhost:8000

uvicorn app.main:app --reload --port 8000
```

API disponible sur http://localhost:8000/api/docs.

### 3. Frontend

```bash
cd frontend
npm install
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api" > .env.local
npm run dev
```

Front disponible sur http://localhost:3000.

### 4. ETL (optionnel)

```bash
cd healthai_etl
pip install -r requirements.txt
python -m healthai_etl.cli all --truncate
```

---

## Configuration

Variables d'env principales (voir `.env.example`) :

| Variable | Valeur par défaut | Description |
|---|---|---|
| `DB_HOST` | `db` (Docker) / `127.0.0.1` (local) | Hôte MariaDB |
| `DB_USER` / `DB_PASSWORD` | `healthai` / `healthai` | Identifiants BDD |
| `DB_NAME` | `healthai_coaching` | Nom de la base |
| `JWT_SECRET_KEY` | `change-me-local-dev` | **À CHANGER en prod** |
| `MEDIA_ROOT` | `data` | Racine des fichiers statiques (GIFs, photos) |
| `MEDIA_BASE_URL` | `http://localhost:8000` | URL publique pour servir les assets |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api` | URL backend visible par le front |

---

## Architecture des rôles

- **UTILISATEUR** : suit son sport, sommeil, nutrition, biométrie, objectifs
- **ADMIN** : gestion des catalogues (exercices, aliments), supervision ETL et qualité
- **SUPER_ADMIN** : gestion des utilisateurs, organisations, sources de données, règles qualité

## Endpoints clés

- `POST /api/auth/login` — connexion
- `GET /api/me/profile` — profil utilisateur courant
- `GET /api/me/seances` — historique séances
- `POST /api/ai/analyse-repas` — analyse photo (Gemini), persistée dans MongoDB
- `GET /api/ai/analyse-repas/history` — relecture NoSQL des analyses (`food_analyses`)
- `POST /api/ai/recommandations` — recommandations (Ollama), persistées dans MongoDB
- `GET /api/ai/recommandations/history` — relecture NoSQL des recommandations (`recommendations`)
- `GET /api/admin/dashboard/charts/*` — KPIs admin
- `GET /api/super-admin/monitoring/*` — monitoring ETL
- `/media/exercises/*`, `/media/organisations/*`, `/media/progression/*` — fichiers statiques

Voir Swagger pour la liste complète : http://localhost:8000/api/docs

---

## Tests

```bash
cd backend
pytest
```

---

## Licence

Projet académique MSPR — CDA-DIADS 2025-2026.
