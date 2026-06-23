# Roadmap Backend — HealthAI Coaching

Document de pilotage : il aligne la **cible architecturale** décrite dans `message.txt`
(plateforme orientée rôles UTILISATEUR / ADMIN / SUPER_ADMIN, contrat REST paginé,
dashboards, ETL, qualité, exports) avec **l'état actuel** du backend Python/FastAPI
(`backend/app/`).

> Note de stack : la spec `message.txt` propose **NestJS + Prisma**. Le backend
> existant est en **FastAPI + SQLAlchemy 2.0 + MySQL**. La roadmap reste sur ce
> stack (réécriture coûteuse, équivalence fonctionnelle complète possible).
> Ce qui change : `class-validator` → Pydantic v2, `Pino` → `loguru`/`structlog`,
> `Prisma` → SQLAlchemy + Alembic, `Swagger Nest` → OpenAPI auto FastAPI.

---

## 1. État actuel (snapshot)

### Implémenté ✅
- FastAPI app factory (`app/main.py`) + CORS + handlers d'erreurs
- Auth JWT maison (HS256) + PBKDF2 (210k it.), refresh cookie HttpOnly
  - `POST /api/auth/login`, `POST /api/auth/logout`, `POST /api/auth/refresh`, `GET /api/auth/me`
- RBAC via dependency `require_roles(*roles)` (UTILISATEUR / ADMIN / SUPER_ADMIN)
- Filtrage owner automatique pour rôle UTILISATEUR
- Moteur CRUD générique (`app/modules/resources.py`) — 17 ressources auto-exposées
- Schémas Pydantic auto-générés depuis SQLAlchemy (`build_schema`)
- Soft-delete intelligent (introspection FK)
- Pagination uniforme `?page=&page_size=` → `{data, meta}`
- 3 dashboards de base : `/api/me/dashboard`, `/api/admin/dashboard`, `/api/super-admin/dashboard`
- 17 modèles SQLAlchemy (IAM, ETL, santé, sport, nutrition)
- Validation métier `JournalAlimentaire` (XOR plat/aliment), `SeanceComplete`
- Dockerfile prod (`python:3.12-slim`, healthcheck `/health`)

### Manquant / divergent ❌
- `forgot-password` / `reset-password`
- `PUT /api/me/profile`, `PUT /api/me/password`
- Endpoints "charts" et "kpis" dédiés (séries temporelles, agrégats)
- Détail séance avec exercices, détail plat avec lignes, latest mesures, objectif actif
- Vues admin par utilisateur (`/admin/utilisateurs/{id}/resume|biometrie|...`)
- Workflow lots ETL (statut, raw/staging/controles/impacts, compare avant/après)
- Toute la couche Qualité riche (KPIs, charts par niveau/décision/source/lot/timeline)
- **Exports CSV / Excel / PDF** (aucune dépendance, aucun endpoint)
- Endpoints super-admin spécifiques (orgs, sources, monitoring) — actuellement génériques
- Tri serveur (`sortBy`, `sortOrder`)
- Format de réponse paginée enrichi avec bloc `filters`
- Format d'erreur aligné spec (`{statusCode, message, errors{}}`)
- Distinction droits ADMIN vs SUPER_ADMIN sur orgs/sources sensibles
- Migrations (Alembic absent) — schéma piloté par dump SQL
- Logging applicatif structuré
- Tests (dossier `tests/` sans `conftest.py` ni couverture visible)
- Rate limiting
- OpenAPI tags / descriptions soignés pour soutenance
- Documentation OpenAPI exposée et propre

---

## 2. Conventions cibles à harmoniser (transverse)

À traiter dans le Sprint 1 bis pour ne pas avoir à revenir dessus.

### 2.1 Format de réponse paginée
Spec : `{ data, meta:{page,pageSize,total,totalPages}, filters:{search,sortBy,sortOrder} }`.
Actuel : `{ data, meta:{page,page_size,total,total_pages} }`.

➡ Décision : **garder snake_case** (cohérent Python) mais **ajouter le bloc `filters`**
échoant la requête. Documenter dans README.

### 2.2 Format d'erreur
Spec : `{ statusCode, message, errors{} }`.
Actuel : `{ error:{code,message,details} }`.

➡ Décision : conserver `{error:{...}}` (plus structuré) et documenter le mapping
côté frontend dans `lib/api/`. Ajouter le `statusCode` HTTP au payload pour faciliter.

### 2.3 Tri serveur
Ajouter `?sortBy=&sortOrder=asc|desc` à `PaginationParams` ; valider en whitelist
par ressource pour éviter l'injection de colonnes.

### 2.4 Filtres standards
- `search` — full-text simple (LIKE) sur 1-3 colonnes whitelistées
- `dateFrom`, `dateTo` — sur la colonne temporelle naturelle de la ressource
- Filtres métier — DTO Pydantic dédié par ressource

### 2.5 Politique d'accès affinée
| Resource             | UTILISATEUR | ADMIN | SUPER_ADMIN |
|---------------------|:-----------:|:-----:|:-----------:|
| /me/*               | ✅ propre  | -     | -           |
| Catalogue (exercices, aliments) | R | R | R   |
| Référentiels admin (regles-qualite, exercices CRUD, aliments CRUD) | - | RW | RW |
| Lots ETL workflow   | -          | RW    | RW          |
| Organisations       | -          | R     | RW          |
| Sources de données  | -          | R     | RW          |
| Monitoring global   | -          | -     | R           |
| Exports             | -          | RW    | RW          |

➡ Introduire `require_roles("ADMIN","SUPER_ADMIN")` vs `require_roles("SUPER_ADMIN")`
distincts ; auditer chaque endpoint.

### 2.6 Logging
Adopter `loguru` (1 ligne d'install) ou `structlog`. Middleware d'access log JSON
(method, path, status, duration_ms, user_id si auth, request_id).

### 2.7 OpenAPI
- `tags` cohérents par module (Auth, Me, Admin/Users, Admin/ETL, Admin/Quality, Admin/Exports, SuperAdmin)
- `summary` et `response_model` sur tout endpoint
- Exemples (`examples=`) sur les schémas critiques
- `/docs` activé en non-prod, désactivé en prod (ou protégé)

---

## 3. Roadmap par sprint

Légende : ✅ déjà fait · 🟡 partiel · ❌ à faire

### Sprint 1 — Socle technique (durcir l'existant) ✅ livré
Objectif : avoir un socle propre et documenté.

- ✅ Auth login/logout/refresh/me
- ✅ JWT + PBKDF2 + cookie HttpOnly
- ✅ RBAC dependency
- ✅ Pagination uniforme
- ✅ CRUD générique
- ✅ **Tri serveur** (`sort_by`/`sort_order` dans `PaginationParams`, whitelist par ressource via `ResourceConfig.sortable_fields`)
- ✅ **Recherche serveur** (`search` + `searchable_fields` whitelistés, LIKE)
- ✅ **Bloc `filters`** dans la réponse paginée (`filters_echo`)
- ✅ **Logging structuré** (loguru + fallback stdlib + `RequestLogMiddleware` avec `x-request-id`)
- ✅ **`forgot-password` / `reset-password`** (JWT type `reset` court, anti-énumération)
- ✅ **Rate limiting** sur `/auth/login` (10/min), `/auth/forgot-password` (5/min), `/auth/reset-password` (10/min) via slowapi (fallback no-op)
- ✅ **`PUT /me/profile`** + **`PUT /me/password`** (champs restreints, vérif ancien mdp)
- ❌ **Alembic** : init + baseline migration depuis le dump SQL → reporté Sprint 6
- ❌ **OpenAPI propre** : tags, descriptions, response_model partout → en cours, par sprint métier
- ❌ **Tests** : `conftest.py` (DB de test, fixture `client`, fixture `admin_token`/`user_token`), 1 test smoke par module → reporté Sprint 6

**Livrable Sprint 1** : socle prêt à recevoir les sprints métier sans dette transverse. ✅

---

### Sprint 2 — Espace utilisateur ✅ livré
Fichiers cibles : `app/modules/me.py`, `app/services/me_metrics.py`, `app/schemas/me.py`.

- ✅ `GET /api/me/dashboard` (existant — à enrichir au S6)
- ✅ Listes `/api/me/{objectifs, mesures-biometriques, sommeil-sante, seances, plats, journal-alimentaire, photos}` (avec sort/search/filters)
- ✅ `GET /api/me/profile`, `PUT /api/me/profile` (UpdateProfileRequest restrictif)
- ✅ `PUT /api/me/password` (vérif ancien + hash PBKDF2)
- ✅ `GET /api/me/kpis` (poids/IMC/dernier sommeil, séances 30j, calories brûlées 30j, calories du jour, objectif actif, photos total, plats 30j)
- ✅ `GET /api/me/objectifs/actif` (filtre `actif_unique`)
- ✅ `GET /api/me/mesures-biometriques/latest`
- ✅ `GET /api/me/mesures-biometriques/charts?metric=&date_from=&date_to=&granularity=day|week|month`
- ✅ `GET /api/me/sommeil-sante/latest`
- ✅ `GET /api/me/sommeil-sante/charts?metric=...`

**Whitelist métriques biométrie** : `poids_kg, imc, taux_masse_grasse, bpm_repos, bpm_moyen, bpm_max, eau_l`
**Whitelist métriques sommeil** : `duree_sommeil_h, qualite_sommeil_score, stress_score, pas_jour, frequence_cardiaque_bpm, activite_physique_min_jour`

Pattern recommandé : créer `app/services/biometrie_service.py`, `sommeil_service.py`,
`dashboard_service.py` qui prennent une `Session` + `utilisateur_id` + `DateRange`
et renvoient des dicts agrégés. Endpoints minces.

**Livrable Sprint 2** : espace user complet pour démo soutenance.

---

### Sprint 3 — Sport & nutrition ✅ livré
Fichiers cibles : `app/modules/me.py`, `app/services/me_sport.py`, `app/services/me_nutrition.py`, `app/modules/exercices_extra.py`.

- ✅ Listes `seances`, `plats`, `journal-alimentaire`, `exercices`, `aliments`
- ✅ `GET /api/me/seances/{seance_id}` (ownership 404 si autre user)
- ✅ `GET /api/me/seances/{seance_id}/exercices` (jointure `seance_exercice` + `exercice`, ordre exercices, GIFs multi-rés)
- ✅ `GET /api/me/seances/kpis` (nb total/7j/30j, durée moyenne 30j, calories 30j, top 5 types)
- ✅ `GET /api/me/seances/charts?date_from=&date_to=&granularity=day|week|month` (nb, calories, durée par bucket)
- ✅ `GET /api/me/plats/{plat_id}` + cohérence `calories_totales_kcal` vs somme lignes (`coherence_calories: bool`)
- ✅ `GET /api/me/plats/{plat_id}/lignes` (jointure `journal_alimentaire` + `aliment` left-outer)
- ✅ `GET /api/me/nutrition/charts?date_from=&date_to=&granularity=...` (calories/bucket + top 10 aliments + répartition par type_repas)
- ✅ `GET /api/exercices/filters` (body_parts, target_muscles, equipements distincts) — registered avant le CRUD générique pour éviter `/exercices/{item_id}`
- ⏭️ `GET /api/me/photos-progression` — couvert par `/api/me/photos` existant (alias)

**Livrable Sprint 3** : pages nutrition / sport / catalogue exercices / photos opérationnelles.

---

### Sprint 4 — Admin ETL & qualité ✅ livré
Fichiers : `app/modules/admin.py`, `app/services/{admin_users,admin_etl,admin_quality,admin_dashboard}.py`.

#### 4.1 Admin Users
- ✅ CRUD utilisateurs (générique)
- ✅ `GET /api/admin/utilisateurs` (join organisation, search, filtres role/statut/organisation_id)
- ✅ `PATCH /api/admin/utilisateurs/{id}/statut` (whitelist ACTIF/INACTIF/SUSPENDU)
- ✅ `GET /api/admin/utilisateurs/{id}/resume` (snapshot 360° : compteurs + derniers événements)
- ⏭️ Vues paginées par user (mesures/sommeil/seances/...) — couvert par les CRUD génériques avec filtre `?utilisateur_id=` côté front (à durcir au S6)

#### 4.2 ETL Executions / Lots
- ✅ CRUD générique sur les 5 tables ETL
- ✅ `GET /api/admin/etl/executions/{id}` (jointure source + lots associés)
- ✅ `PATCH /api/admin/etl/lots/{id}/statut` (workflow EN_ATTENTE/VALIDE/REJETE/ARCHIVE, audit `valide_par_utilisateur_id` + `valide_le`)
- ✅ `GET /api/admin/etl/lots/{id}/resume` (compteurs raw/staging/controles/bloquants)
- ✅ `GET /api/admin/etl/lots/{id}/raw?entite=&page=&page_size=`
- ✅ `GET /api/admin/etl/lots/{id}/staging?entite=`
- ✅ `GET /api/admin/etl/lots/{id}/controles`
- ✅ `GET /api/admin/etl/lots/{id}/impacts` (compteur par table métier)
- ✅ `GET /api/admin/etl/compare?lot_id=&entite=&ref_externe=` (**vue narrative avant/après** : raw + staging + règles déclenchées avec détails)

#### 4.3 Qualité
- ✅ `GET /api/admin/qualite/controles` (filtres: niveau, type_controle, decision_finale, entite, lot_id, execution_id, regle_id, nom_champ, etape_pipeline, source_id, date_from, date_to)
- ✅ `GET /api/admin/qualite/controles/{id}`
- ✅ `GET /api/admin/qualite/kpis` (nb total, bloquants, rejets, ratios, entités distinctes)
- ✅ Charts : `levels`, `decisions`, `top-rules`, `top-fields`, `by-source`, `by-lot`, `timeline` (granularité day/week/month)

#### 4.4 Référentiels admin
- ⏭️ Couvert par les CRUD génériques `/api/aliments`, `/api/exercices`, `/api/regles-qualite` (RBAC ADMIN+)

#### 4.5 Dashboard admin
- ✅ `/api/admin/dashboard` basique
- ✅ Charts : `quality-by-source`, `rejects-by-lot`, `imports-volume` (granularité), `users-by-organisation`, `top-rules`

**Livrable Sprint 4** : centre névralgique admin avec narration ETL avant/après — **point fort soutenance**. ✅

---

### Sprint 5 — Super-admin & exports ✅ livré (CSV uniquement, XLSX/PDF reportés)
Fichiers : `app/modules/super_admin.py`, `app/modules/exports.py`, `app/services/exports.py`, `app/services/admin_dashboard.py` (volumes/quality/failed/blocked).

#### 5.1 Super-admin
- ⏭️ Restreindre `/api/organisations` et `/api/sources-donnees` à SUPER_ADMIN en mutation : à durcir au S6 (CRUD générique partagé pour l'instant via `CRUD_ROLES = (ADMIN, SUPER_ADMIN)`)
- ✅ `GET /api/super-admin/dashboard` (de base depuis dashboards.py)
- ✅ `GET /api/super-admin/dashboard/charts/{quality-by-organisation, volumes-by-source}`
- ✅ `GET /api/super-admin/monitoring/etl` (exécutions échec + lots bloqués)
- ✅ `GET /api/super-admin/monitoring/qualite` (qualité par source + volumes par source)

#### 5.2 Exports CSV (streaming)
- ✅ `GET /api/admin/exports/{dataset}` → `StreamingResponse` (csv stdlib, pas de pandas)
- ✅ Datasets supportés : `utilisateurs, biometrie, sommeil, sport, nutrition, qualite, executions, lots, plats`
- ✅ Header `Content-Disposition: attachment; filename="<dataset>_<ts>.csv"`
- ❌ XLSX → S6 (besoin `openpyxl`)
- ❌ PDF synthèse → S6 (besoin `weasyprint`/`reportlab`)
- ⏭️ Filtres dynamiques d'export (date_from/date_to/utilisateur_id) → S6

**Livrable Sprint 5** : super-admin monitoring + exports CSV opérationnels. XLSX/PDF reportés au polish S6.

---

### Sprint 6 — Finition MSPR
- ❌ Couverture tests ≥ 60% sur les services (`pytest-cov`)
- ❌ Tests d'intégration sur le happy path de chaque rôle
- ❌ Seed de démo (`scripts/seed_demo.py`) : 1 org, 3 users (1 par rôle), 30j de mesures, 10 séances, 20 plats, 1 exécution ETL avec contrôles
- ❌ Hardening : remplacer JWT maison par `pyjwt` (ou `python-jose`) — **important sécu**
- ❌ Documentation API : `README.md` à jour + exemple curl par rôle
- ❌ Script de soutenance : `make demo` qui lance docker-compose + seed + ouvre `/docs`
- ❌ Audit : revue croisée des dépendances `require_roles` sur tous les endpoints

---

## 4. Dette technique transverse à planifier

| Item | Sprint suggéré | Effort |
|------|---------------|--------|
| Remplacer JWT maison par `pyjwt` | S6 | S |
| Alembic + baseline migration | S1 | M |
| Logging structuré + request id | S1 | S |
| Rate limiting auth | S1 | S |
| Tests + conftest | S1 → S6 | L (étalé) |
| Cache (Redis ?) sur catalogues lecture-lourde (exercices, aliments) | S6 / bonus | M |
| Pré-calcul agrégats dashboard (vue matérialisée ou job) si volumétrie ↗ | bonus | L |
| Couche service (extraction logique hors endpoints) | S2 → S5 (au fil) | M |

---

## 5. Risques et points d'attention

1. **JWT maison** — risque crypto. À remplacer en S6 avant soutenance (sinon ça
   sera la première remarque du jury sécurité).
2. **`build_schema` dynamique** — couplage fort modèle DB / API. Acceptable pour
   le CRUD admin, **inadapté** pour les endpoints métier (`/me/*`, charts, exports)
   où il faut des DTOs explicites.
3. **Pas d'Alembic** — chaque évolution de schéma est risquée. Prioriser S1.
4. **Dashboards calculés à la volée** — OK tant que la BDD reste petite. Prévoir
   index sur `mesure_biometrique(utilisateur_id, mesure_le)`,
   `mesure_sommeil_sante(utilisateur_id, mesure_le)`,
   `seance_entrainement(utilisateur_id, date_seance)`,
   `journal_alimentaire(plat_id)`,
   `controle_qualite_donnee(execution_etl_id, lot_donnees_id, niveau, decision_finale)`.
5. **Exports PDF** = chantier non négligeable. Si temps serré, **livrer CSV+XLSX**
   au S5 et reporter PDF au S6/bonus.
6. **`/admin/etl/compare`** — le morceau le plus narratif pour la soutenance,
   mais aussi le plus complexe (jointure 3 niveaux + payloads JSON). Prototype
   tôt en S4.

---

## 6. Ordre d'attaque conseillé (priorité MSPR)

> Si le temps manque, livrer dans cet ordre — chaque palier est une démo cohérente.

1. **S1 socle hardening** (tri/filtres/logging/Alembic/forgot-password/tests squelette)
2. **S2 espace user complet** (profile + dashboard + charts) — *première démo qui claque*
3. **S4.1 + S4.2 ETL admin** (executions, lots, détail lot, compare avant/après) — *narration ETL*
4. **S4.3 Qualité** (KPIs + 3 charts clés : levels, top-rules, timeline)
5. **S3 sport & nutrition détaillé** (détail séance, détail plat, photos)
6. **S5.2 Exports CSV+XLSX** (sans PDF)
7. **S5.1 Super-admin** (dashboard global + monitoring)
8. **S6 polish** (PDF, JWT lib, tests, seed démo, docs)

---

## 7. Fichiers backend à créer / modifier (synthèse)

### À modifier
- `app/core/pagination.py` — ajouter `sortBy`, `sortOrder`, bloc `filters`
- `app/core/security.py` — remplacer JWT maison par `pyjwt` (S6)
- `app/main.py` — middleware logging, OpenAPI metadata
- `app/modules/api.py` — réorganiser par tags, restreindre orgs/sources à SUPER_ADMIN
- `app/modules/auth.py` — ajouter forgot/reset password
- `app/modules/me.py` — endpoints profile, password, charts, latest, kpis
- `app/modules/dashboards.py` — enrichir les 3 dashboards avec vrais agrégats
- `requirements.txt` — `loguru`, `pyjwt`, `slowapi`, `alembic`, `openpyxl`, `pandas`, `weasyprint`, `pytest-cov`

### À créer
- `app/services/{biometrie,sommeil,seances,nutrition,dashboard,etl,quality,export}_service.py`
- `app/modules/admin/{users,etl,quality,referentiels,exports}.py`
- `app/modules/super_admin/{organisations,sources,monitoring}.py`
- `app/schemas/{me,admin,quality,export}.py` — DTOs explicites par usage
- `alembic/` — env + baseline
- `tests/conftest.py`, `tests/test_*.py` (1 par module)
- `scripts/seed_demo.py`

---

## 8. Critères de done pour la soutenance

- [ ] Auth complète + 3 rôles distincts
- [ ] Espace utilisateur navigable avec dashboard + 5 charts
- [ ] Espace admin avec liste utilisateurs + détail 360°
- [ ] Workflow ETL : exécutions → lots → détail lot → avant/après
- [ ] Qualité : tableau filtrable + 3 charts
- [ ] Super-admin : dashboard global + monitoring
- [ ] Exports CSV + XLSX fonctionnels
- [ ] OpenAPI `/docs` propre, navigable, exemples
- [ ] Seed démo lance la plateforme avec données réalistes
- [ ] Couverture tests > 50% sur services critiques
- [ ] JWT basé sur lib éprouvée
