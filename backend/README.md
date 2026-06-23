# Backend HealthAI Coaching

API REST FastAPI connectee a la base MySQL/MariaDB alimentee par `healthai_etl/`.

## Installation

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

La configuration lit `backend/.env`, `.env`, puis `../healthai_etl/.env` si present.

Variables principales:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=healthai_coaching
JWT_SECRET_KEY=change-me
```

## Lancement

```bash
uvicorn app.main:app --reload
```

Documentation OpenAPI:

- `http://127.0.0.1:8000/api/docs`
- `http://127.0.0.1:8000/api/openapi.json`

## Contrat API

- Auth: `/api/auth/login`, `/api/auth/logout`, `/api/auth/refresh`, `/api/auth/me`
- Espace utilisateur: `/api/me/*`
- Dashboards: `/api/me/dashboard`, `/api/admin/dashboard`, `/api/super-admin/dashboard`
- CRUD MCD: referentiels, profil/sante, sport/nutrition, pilotage ETL.

Les listes retournent:

```json
{ "data": [], "meta": { "page": 1, "page_size": 20, "total": 0, "total_pages": 0 } }
```

Les erreurs retournent:

```json
{ "error": { "code": "validation_error", "message": "...", "details": [] } }
```

## Tests

```bash
pytest
```
