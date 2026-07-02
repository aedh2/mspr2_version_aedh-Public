# Guide de maintenance & exploitation — HealthAI Coach

Ce document couvre le volet **« produire et maintenir »** (blocs 3/4) : intégration
continue, sauvegarde/restauration des données, et commandes d'exploitation.

## 1. Intégration continue (CI/CD)

Pipeline GitHub Actions : [`.github/workflows/ci.yml`](../.github/workflows/ci.yml).

Déclenché à chaque `push` (branches `maintenance`, `main`) et `pull_request` :

| Job | Contenu |
|---|---|
| **Backend · tests** | Python 3.12, `pip install -r backend/requirements.txt`, `pytest` (tests autonomes SQLite en mémoire — aucune base externe requise). |
| **Frontend · build** | Node 22, `npm ci`, `next build` (mêmes conditions que l'image Docker de production). |

Suivi des exécutions : onglet **Actions** du dépôt GitHub.

## 2. Sauvegarde & restauration des données

Les deux bases (MariaDB + MongoDB) sont sauvegardées depuis les conteneurs Docker.

### Sauvegarde

```bash
bash scripts/backup.sh
# ou : make backup
```

Génère `backups/AAAAMMJJ_HHMMSS/` contenant :
- `mariadb_healthai_coaching.sql` — dump SQL (`mariadb-dump`, transaction unique, routines & triggers) ;
- `mongo_healthai_nosql.archive` — archive MongoDB (`mongodump --archive`).

### Restauration

```bash
bash scripts/restore.sh backups/AAAAMMJJ_HHMMSS
# ou : make restore DIR=backups/AAAAMMJJ_HHMMSS
```

Restaure MariaDB (import SQL) et MongoDB (`mongorestore --drop`).

> Les dumps ne sont pas versionnés (voir `.gitignore`). Le dossier `backups/` est conservé via `.gitkeep`.

Variables surchargeables : `DB_CONTAINER`, `MONGO_CONTAINER`, `DB_NAME`, `MONGO_DB_NAME`, `MYSQL_ROOT_PASSWORD`.

## 3. Commandes d'exploitation (Makefile)

| Commande | Action |
|---|---|
| `make up` | Démarre toute la stack (build) |
| `make down` | Arrête la stack |
| `make reset` | Réinitialise (supprime les volumes) puis redémarre |
| `make ps` | État des services |
| `make logs` | Logs agrégés (suivi) |
| `make test` | Tests backend (`pytest`) |
| `make backup` | Sauvegarde MariaDB + MongoDB |
| `make restore DIR=...` | Restaure une sauvegarde |

> Scripts et Makefile s'exécutent sous un shell POSIX (Linux, macOS, ou Git Bash / WSL sous Windows).

## 4. Supervision

- `GET /health` expose l'état des deux bases : `{"databases":{"relationnel":"mariadb","documentaire":"ok"}}`.
- Observabilité IA : chaque appel (Gemini/Ollama) est journalisé dans MongoDB (`ai_provider_calls`) → KPI taux de repli, latence, disponibilité.
- Un monitoring de la stack (Prometheus/Grafana) est prévu dans un lot ultérieur.
