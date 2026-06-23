# Roadmap Frontend — HealthAI

Document de cadrage et plan d'exécution pour terminer le frontend HealthAI. Aligné sur la vision produit de `message.txt`, adapté à la stack réellement en place et à la maturité actuelle du code.

---

## 0. État des lieux

### Stack effective (frontend)

- **Next.js 15** (App Router) + **React 19** + **TypeScript 5.8**
- **Tailwind CSS 4** (PostCSS plugin)
- **@tanstack/react-query 5** pour fetch/cache
- **react-hook-form 7** + **Zod 3** pour les formulaires
- **Recharts 2.15** pour les graphes (Recharts retenu, pas ECharts)
- **lucide-react** pour les icônes
- **Playwright** pour les tests e2e
- Pas de `shadcn/ui` installé : composants UI maison dans `src/components/ui/*` (Button, DataTable, Modal, Pagination, MetricCard, ChartCard, StatusBadge, Field/Input/Select/Textarea, états Loading/Error)
- Pas de **zustand** ni de **next-themes** (mode sombre à câbler manuellement si besoin)

> ⚠️ Écart vs `message.txt` : le backend réel est **FastAPI / Python**, pas NestJS. Toutes les routes ci-dessous pointent vers l'API FastAPI (préfixe `/api`). Les noms d'endpoints existants ont été vérifiés dans `backend/app/modules/*.py`.

### Ce qui est déjà en place

```
frontend/
├── app/
│   ├── layout.tsx                      ✅ shell racine
│   ├── login/page.tsx                  ✅
│   ├── me/{layout, dashboard, mesures-biometriques, sommeil, seances, seances/[id], journal-alimentaire, nutrition/plats/[id]}
│   ├── admin/{layout, dashboard, utilisateurs, executions-etl, controles-qualite}
│   └── super-admin/{layout, dashboard, organisations}
├── src/
│   ├── lib/{api.ts, config.ts, format.ts, permissions.ts}
│   ├── components/{providers, role-guard, app-shell, ui/*}
│   ├── features/{auth, me, admin, users, etl, qualite, nutrition, seances}
│   ├── hooks/use-paged-api.ts
│   └── types/domain.ts
```

### Manques fonctionnels critiques (vs vision message.txt)

**Espace utilisateur** : `/profile`, `/objectifs`, `/exercices`, `/exercices/[id]`, `/aliments`, `/photos`, `/nutrition` (page liste plats), routes de reset password.
**Espace admin** : fiche utilisateur `/admin/utilisateurs/[id]` + onglets, détail exécution `/admin/etl/executions/[id]`, liste `/admin/etl/lots`, détail lot, page `/admin/etl/compare` (avant/après), `/admin/aliments`, `/admin/exercices`, `/admin/regles-qualite`, `/admin/exports`.
**Espace super admin** : `/super-admin/sources`, `/super-admin/monitoring`, détail orga `/super-admin/organisations/[id]`.
**Transverses** : pas de breadcrumb, pas de dark mode, pas d'EntityDrawer, pas de DateRangeFilter générique, pas de drill-down, pas d'export PDF côté front.

---

## 1. Principes directeurs

1. **Aligner sur le backend existant** — relire `backend/app/modules/*.py` avant chaque sprint, pas réinventer les routes.
2. **App Router strict** — un fichier `page.tsx` par route, le composant lourd vit dans `src/features/<domaine>/`. Le pattern existant (`MeDashboardPage` exporté depuis `me-pages.tsx`) est conservé mais on **éclate** ce fichier monolithique en sous-modules dès qu'un domaine dépasse ~150 lignes.
3. **TanStack Query partout** — `usePagedApi` pour les listes, `useQuery` pour les agrégats, `useMutation` pour les écritures. Clé de cache = chemin d'API.
4. **RHF + Zod** pour 100 % des formulaires, schéma à côté du formulaire.
5. **Composants UI maison d'abord** — on étoffe `src/components/ui/*`. shadcn/ui n'est pas installé et on évite de l'introduire en cours de route (coût migration > bénéfice à ce stade).
6. **Recharts** pour tous les graphes (cohérence). On factorise les charts dans `src/components/charts/`.
7. **Garde de rôle** systématique via `<RoleGuard>` dans chaque layout (`me`, `admin`, `super-admin`) — déjà câblé, à vérifier.

---

## 2. Arborescence cible

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx                              → redirige selon rôle
│   ├── login/page.tsx
│   ├── forgot-password/page.tsx              🆕
│   ├── reset-password/page.tsx               🆕
│   ├── me/
│   │   ├── layout.tsx
│   │   ├── dashboard/page.tsx
│   │   ├── profile/page.tsx                  🆕
│   │   ├── objectifs/page.tsx                🆕
│   │   ├── mesures-biometriques/page.tsx
│   │   ├── sommeil/page.tsx
│   │   ├── seances/page.tsx
│   │   ├── seances/[id]/page.tsx
│   │   ├── exercices/page.tsx                🆕
│   │   ├── exercices/[id]/page.tsx           🆕
│   │   ├── nutrition/page.tsx                🆕 (liste plats)
│   │   ├── nutrition/plats/[id]/page.tsx
│   │   ├── aliments/page.tsx                 🆕
│   │   ├── journal-alimentaire/page.tsx
│   │   └── photos/page.tsx                   🆕
│   ├── admin/
│   │   ├── layout.tsx
│   │   ├── dashboard/page.tsx
│   │   ├── utilisateurs/page.tsx
│   │   ├── utilisateurs/[id]/page.tsx        🆕  (avec onglets)
│   │   ├── etl/
│   │   │   ├── executions/page.tsx           🆕 (renomme l'actuel)
│   │   │   ├── executions/[id]/page.tsx      🆕
│   │   │   ├── lots/page.tsx                 🆕
│   │   │   ├── lots/[id]/page.tsx            🆕
│   │   │   └── compare/page.tsx              🆕
│   │   ├── qualite/page.tsx                  🆕 (renomme controles-qualite)
│   │   ├── aliments/page.tsx                 🆕
│   │   ├── exercices/page.tsx                🆕
│   │   ├── regles-qualite/page.tsx           🆕
│   │   └── exports/page.tsx                  🆕
│   └── super-admin/
│       ├── layout.tsx
│       ├── dashboard/page.tsx
│       ├── organisations/page.tsx
│       ├── organisations/[id]/page.tsx       🆕
│       ├── sources/page.tsx                  🆕
│       └── monitoring/page.tsx               🆕
└── src/
    ├── components/
    │   ├── ui/             (existant, à étoffer)
    │   ├── layout/         🆕 (Breadcrumb, SidebarNav, RoleHeader)
    │   ├── charts/         🆕 (LineSeries, BarSeries, PieSeries, Heatmap, KpiCard)
    │   ├── tables/         🆕 (FilterBar, ColumnVisibility, EmptyRow)
    │   ├── filters/        🆕 (DateRangeFilter, SelectFilter, SearchFilter)
    │   ├── forms/          🆕 (FormField, FormError, FormSection)
    │   └── feedback/       🆕 (EntityDrawer, ConfirmDialog déjà présent dans ui/modal.tsx)
    ├── features/
    │   ├── auth/
    │   ├── me/
    │   │   ├── pages/      🆕 éclater me-pages.tsx en MeDashboard.tsx, Biometrie.tsx, Sommeil.tsx, Seances.tsx, SeanceDetail.tsx, Nutrition.tsx, Journal.tsx, PlatDetail.tsx, Profile.tsx, Objectifs.tsx, Exercices.tsx, ExerciceDetail.tsx, Aliments.tsx, Photos.tsx
    │   │   └── hooks/
    │   ├── admin/
    │   │   ├── pages/      🆕 (idem)
    │   │   └── hooks/
    │   ├── super-admin/    🆕
    │   ├── etl/            (existant)
    │   ├── qualite/
    │   ├── nutrition/
    │   ├── seances/
    │   ├── exercices/      🆕
    │   ├── aliments/       🆕
    │   ├── photos/         🆕
    │   ├── exports/        🆕
    │   └── organisations/  🆕
    ├── hooks/
    │   ├── use-paged-api.ts
    │   ├── use-date-range.ts        🆕
    │   ├── use-debounced-value.ts   🆕
    │   └── use-export.ts            🆕
    ├── lib/
    │   ├── api.ts
    │   ├── config.ts
    │   ├── format.ts
    │   ├── permissions.ts
    │   ├── routes.ts                🆕 (constantes routes + libellés)
    │   └── theme.ts                 🆕 (palette + dark mode)
    └── types/
        └── domain.ts
```

---

## 3. Cartographie des endpoints (vérifiée backend)

Référence : `backend/app/modules/*.py`. Le frontend doit consommer **ces** chemins. Les écarts avec `message.txt` sont notés.

### Auth — `auth.py`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `POST /api/auth/refresh`
- `GET  /api/auth/me`
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`

### /me — `me.py`
- `GET  /api/me/dashboard` · `GET /api/me/kpis`
- `GET  /api/me/profile` · `PUT /api/me/profile` · `PUT /api/me/password`
- `GET  /api/me/objectifs` · `GET /api/me/objectifs/actif`
- `GET  /api/me/mesures-biometriques` · `/latest` · `/charts`
- `GET  /api/me/sommeil-sante` · `/latest` · `/charts`  *(⚠ `sommeil-sante`, pas `sommeil`)*
- `GET  /api/me/seances` · `/kpis` · `/charts` · `/{id}` · `/{id}/exercices`
- `GET  /api/me/plats` · `/{id}` · `/{id}/lignes`
- `GET  /api/me/journal-alimentaire`
- `GET  /api/me/nutrition/charts`
- `GET  /api/me/photos`  *(⚠ `photos`, pas `photos-progression`)*

### Catalogues partagés — `resources.py`, `exercices_extra.py`
- `GET /api/utilisateurs` (admin) · `GET /api/utilisateurs/{id}` · `PATCH` · `DELETE`
- `GET /api/organisations` · CRUD
- `GET /api/exercices` · `/{id}` · `/filters`
- `GET /api/aliments` · `/{id}`
- `GET /api/executions-etl` · `/controles-qualite-donnees` (en partie)

### Admin — `admin.py`
- `GET  /api/admin/utilisateurs/{id}/resume`
- `PATCH /api/admin/utilisateurs/{id}/statut`
- `GET  /api/admin/etl/executions/{id}`
- `PATCH /api/admin/etl/lots/{id}/statut`
- `GET  /api/admin/etl/lots/{id}/resume|raw|staging|controles|impacts`
- `GET  /api/admin/etl/compare`
- `GET  /api/admin/qualite/controles[/{id}]` · `/kpis`
- `GET  /api/admin/qualite/charts/{levels|decisions|top-rules|top-fields|by-source|by-lot|timeline}`
- `GET  /api/admin/dashboard/charts/{quality-by-source|rejects-by-lot|imports-volume|users-by-organisation|top-rules}`

### Exports — `exports.py`
- `GET /api/admin/exports/...` (à confirmer module par module)

### Super admin — `super_admin.py`
- `GET /api/super-admin/dashboard`
- `GET /api/super-admin/monitoring/etl|qualite`
- `GET /api/super-admin/dashboard/charts/{quality-by-organisation|volumes-by-source}`

> Les routes manquantes côté backend (sources CRUD, regles-qualite CRUD, exports détaillés) doivent être confirmées avant de bâtir l'UI : ouvrir une issue par manque plutôt que stubber côté front.

---

## 4. Sprints

Chaque sprint = ~3-5 jours. Critère de sortie = pages cibles utilisables + tests Playwright minimaux + revue UI sur Chrome desktop + mobile ≥375px.

### Sprint 1 — Socle UX (transverse) ✅ TERMINÉ

**Objectif** : poser les briques manquantes qui débloquent tout le reste.

- [x] Éclater `src/features/me/me-pages.tsx` et `src/features/admin/admin-pages.tsx` → `pages/` (un fichier par page + `_shared.tsx`). Les anciens fichiers deviennent des barrels de re-export pour compat consumers.
- [x] `src/components/layout/Breadcrumb.tsx` lisant `usePathname()` + map de libellés depuis `lib/routes.ts`. Intégré dans `AppShell`.
- [x] `src/components/filters/DateRangeFilter.tsx` (deux `<input type="date">` + reset, contrôlé) + `src/hooks/use-date-range.ts`.
- [x] `src/hooks/use-debounced-value.ts` pour les recherches.
- [x] `src/components/ui/entity-drawer.tsx` (panneau latéral réutilisable, ESC pour fermer).
- [x] `src/components/charts/{LineSeries,BarSeries,PieSeries,KpiCard}.tsx` — wrappers Recharts (palette commune, gestion empty state).
- [x] `app/page.tsx` → redirige déjà selon rôle via `destinationForRole(user.role)`.
- [x] `app/forgot-password/page.tsx` + `app/reset-password/page.tsx` (RHF + Zod, lien depuis `/login`).
- [x] `RoleGuard` actif dans les trois layouts (`me`, `admin`, `super-admin`) — vérifié.
- [x] `tsc --noEmit` ✔ sans erreur.

**Livrables clés ajoutés** :
- `src/lib/routes.ts` (`ROUTE_LABELS`, `buildBreadcrumbs`)
- `src/components/charts/{palette.ts,LineSeries.tsx,BarSeries.tsx,PieSeries.tsx,KpiCard.tsx,index.ts}`
- `src/components/layout/Breadcrumb.tsx`
- `src/components/filters/DateRangeFilter.tsx`
- `src/components/ui/entity-drawer.tsx`
- `src/hooks/use-debounced-value.ts`, `src/hooks/use-date-range.ts`
- `src/features/me/pages/{_shared,MeDashboard,Biometrie,Sommeil,Seances,Journal}.tsx`
- `src/features/admin/pages/{_shared,AdminDashboard,Users,EtlExecutions,QualityControls,Organisations}.tsx`
- Styles : breadcrumb, empty-chart, kpi-trend ajoutés dans `app/styles.css`

**Critère** : un utilisateur connecté sur chacun des trois rôles atterrit sur son dashboard, voit son menu et son fil d'Ariane. ✅

### Sprint 2 — Espace utilisateur (santé & profil) ✅ TERMINÉ

- [x] `/me/profile` : lecture `GET /api/me/profile` + form `PUT /api/me/profile` (RHF+Zod : nom_utilisateur, prénom, nom, date_naissance, genre, taille_cm) + sous-form `PUT /api/me/password` (ancien/nouveau/confirmation, validation min 8). Note : email non modifiable côté backend (champ retiré du form).
- [x] `/me/objectifs` : carte objectif actif (`GET /api/me/objectifs/actif`, gère 404 → "aucun objectif") + timeline historique paginée (`GET /api/me/objectifs`). Lecture seule.
- [x] `/me/mesures-biometriques` : `DateRangeFilter` contrôlé (filtrage côté client sur `mesure_le`), 3 charts (Poids/IMC, Masse grasse + Eau, BPM repos/moyen/max) avec wrappers `LineSeries`.
- [x] `/me/sommeil` : `DateRangeFilter`, charts Sommeil/Qualité, Stress, Pas (BarSeries), Activité physique (BarSeries) ; `MetricCard` Tension (systolique/diastolique) à partir de `/sommeil-sante/latest`.
- [x] `/me/dashboard` enrichi : Objectif actif, dernière photo de progression, dernières séances (top 4 avec lien détail), derniers repas (top 5).
- [x] Routes `app/me/profile/page.tsx` et `app/me/objectifs/page.tsx` créées, exports ajoutés au barrel `me-pages.tsx`.
- [x] `tsc --noEmit` ✔ sans erreur.

### Sprint 3 — Sport & nutrition ✅ TERMINÉ

- [x] `/me/seances` : filtres type (select dérivé des types existants) + calories minimum, charts `SessionsPerWeek` (BarSeries, granularité semaine) et `BurnedCalories` (LineSeries, granularité jour) depuis `/api/me/seances/charts`.
- [x] `/me/seances/[id]` : ajout au-dessus de la table des 3 charts `Calories par exercice`, `Duree par exercice`, `Volume par exercice` (BarSeries) calculés depuis `/api/me/seances/{id}/exercices`.
- [x] `/me/exercices` : grille (cartes GIF 180px) + recherche debouncée (300ms) + filtres `body_part_principale`, `muscle_cible_principal`, `equipement_principal` alimentés via `/api/exercices/filters` (hook `useExerciceFilters`). Liste paginée via `/api/exercices`.
- [x] `/me/exercices/[id]` : hero metadata + onglets GIF (180/360/720/1080) + instructions parsées depuis `instructions_json` + parse JSON pour body_parts/target_muscles/secondary/equipments. Hook `useExercice`.
- [x] `/me/nutrition` : liste paginée `/api/me/plats` distincte du journal (badge cohérence calories par ligne).
- [x] `/me/nutrition/plats/[id]` : ajout `CaloriesByFoodChart` (BarSeries) au-dessus du tableau lignes ; contrôle visuel cohérence (callout `incoherent`) déjà présent.
- [x] `/me/aliments` : `/api/aliments` paginé + recherche debouncée + filtre catégorie (dérivé de la page courante) + colonnes nutrition.
- [x] `/me/photos` : `BeforeAfterGallery` (1ère vs dernière chronologiquement) + timeline complète. Styles `.before-after`, `.exercise-grid`, `.exercise-card` ajoutés.
- [x] Navigation latérale enrichie : ajout `Exercices`, `Plats`, `Aliments` (icônes Dumbbell, UtensilsCrossed, Apple). Renommage de l'entrée Nutrition existante en `Journal alimentaire`.
- [x] Types ajoutés : `Exercice`, `ExerciceFilters`, `Aliment`. Hooks ajoutés : `src/features/exercices/hooks.ts`.
- [x] Routes app : `/me/exercices`, `/me/exercices/[id]`, `/me/nutrition`, `/me/aliments`, `/me/photos`.
- [x] `tsc --noEmit` ✔ sans erreur.

### Sprint 4 — Admin métier & ETL ✅ TERMINÉ

- [x] `/admin/dashboard` : KPI conservés + 5 charts (`quality-by-source`, `rejects-by-lot`, `imports-volume` 90j 3 séries, `users-by-organisation` Pie, `top-rules` Bar).
- [x] `/admin/utilisateurs/[id]` : header (identité, rôle, statut, organisation) + form `PATCH /admin/utilisateurs/{id}/statut` + onglets (Résumé, Biométrie, Sommeil, Séances, Nutrition, Photos, Objectifs). Onglet Résumé = compteurs + derniers évènements + profil ; les autres onglets affichent une note "endpoint dédié à confirmer côté backend" (voir Risques).
- [x] `/admin/etl/executions` : page déplacée sous `/admin/etl/executions/` (lien ID → détail). L'ancienne route `/admin/executions-etl` reste en place pour compat mais sortie de la nav.
- [x] `/admin/etl/executions/[id]` : header + métriques (lignes lues/valides/invalides/rejets) + table des lots associés avec liens vers `/admin/etl/lots/[id]`.
- [x] `/admin/etl/lots` : table paginée `/api/lots-donnees` + filtre statut, lien vers détail.
- [x] `/admin/etl/lots/[id]` : `LotSummaryCard` (resume + compteurs raw/staging/contrôles/bloquants) + onglets RawDataTable (`/raw`), StagingTable (`/staging`), QualityControlsTable (`/controles`), GeneratedDataImpactCards (`/impacts`).
- [x] `/admin/qualite` (nouvelle route, ancienne `/admin/controles-qualite` conservée pour compat) : 6 KPI cards (`/qualite/kpis`) + filtres niveau/decision/entite + 7 charts (levels Pie, decisions Pie, top-rules Bar, top-fields Bar, by-source Bar, by-lot Bar, timeline Line) + table paginée des contrôles.
- [x] `/admin/etl/compare` : `BeforeAfterViewer` 3 colonnes (raw payload pretty-print / staging normalisé pretty-print + meta validation / décision qualité = table contrôles + règle déclenchée). Form de sélection `lot_id`, `entite`, `ref_externe`.
- [x] Liens cliquables : Users → fiche utilisateur ; Executions → détail ; Lots → détail.
- [x] Navigation : ajout `Lots ETL`, `Avant / Apres ETL` ; remplacement `/admin/executions-etl` → `/admin/etl/executions` ; `/admin/controles-qualite` → `/admin/qualite`.
- [x] Types ajoutés : `LotDonnees`, `AdminQualityKpis` ; enrichissement `ControleQualite` (regle_id, ref_externe, ref_ligne, valeur_observee, valeur_corrigee).
- [x] CSS : `.tab-bar`, `.json-pre`, `.compare-grid`.
- [x] `tsc --noEmit` ✔ sans erreur.

**Risques / TODO backend identifiés (à ouvrir en tickets)**

- Les tabs Bio/Sommeil/Séances/Nutrition/Photos/Objectifs de la fiche admin utilisateur affichent un placeholder : il manque côté backend une lecture filtrée par utilisateur (`/api/admin/utilisateurs/{id}/{entity}` ou support `?utilisateur_id=` sur les CRUDs `/api/mesures-biometriques`, `/api/seances-entrainement`, `/api/plats`, `/api/progression-photos`, `/api/objectifs-utilisateur`). Aujourd'hui le filtre owner ne s'applique qu'au rôle `UTILISATEUR`.

### Sprint 5 — Référentiels admin, super admin, exports ✅ TERMINÉ

- [x] `/admin/aliments` : CRUD complet (modale RHF+Zod, recherche debouncée) — pattern `OrganisationsPage` étendu (champs nutrition).
- [x] `/admin/exercices` : lecture paginée + recherche + édition métadonnées (`PATCH /api/exercices/{id}`) via modale RHF+Zod.
- [x] `/admin/regles-qualite` : table + filtres (recherche, sévérité, actif) + toggle `actif` via `PATCH /api/regles-qualite/{id}`.
- [x] `/admin/exports` : grille de cartes datasets (utilisateurs, biométrie, sommeil, sport, nutrition, plats, qualité, exécutions, lots) + `useExport()` qui télécharge le CSV via `fetch` + `URL.createObjectURL` avec auth Bearer.
- [x] `/super-admin/dashboard` : `MetricCard` globaux (utilisateurs, admins, exécutions, qualité min/max), `QualityByOrganisationChart` (BarSeries), `VolumesBySourceChart` (BarSeries 3 séries) et `GlobalHeatmap` (grille SVG/CSS coloriée par taux qualité × volume).
- [x] `/super-admin/organisations/[id]` : header + KPIs (utilisateurs, admins, créée le) + formulaire d'édition + table membres avec lien fiche utilisateur.
- [x] `/super-admin/sources` : table paginée `/api/sources-donnees` + modale CRUD + toggle `actif`.
- [x] `/super-admin/monitoring` : `FailedExecutionsTable` + `BlockedLotsTable` (liens vers détails ETL) + `AbnormalRejectRateChart` (BarSeries calculé `nb_rejets/lignes_lues`).
- [x] Navigation enrichie : ajout `Catalogue aliments`, `Catalogue exercices`, `Regles qualite`, `Exports`, `Dashboard global`, `Sources`, `Monitoring`.
- [x] Types ajoutés : `RegleQualite`, `SourceDonnees`, `SuperAdminDashboard`, `FailedExecution`, `BlockedLot`.
- [x] Hook ajouté : `src/hooks/use-export.ts`.
- [x] Barrel `src/features/super-admin/super-admin-pages.tsx` créé.
- [x] CSS : `.export-grid`, `.export-card`, `.heatmap-grid`, `.heatmap-cell` ajoutés.
- [x] `tsc --noEmit` ✔ sans erreur.

### Sprint 6 — Polish & soutenance MSPR

- [ ] **Mode sombre** via classe `dark:` Tailwind + toggle persistant (`localStorage`).
- [ ] **Drill-down** : un clic sur un KPI admin filtre la table associée (query string).
- [ ] **Comparaison de périodes** sur biométrie/sommeil (`?compareFrom=&compareTo=`).
- [ ] **Export PDF dashboard utilisateur** : `react-to-pdf` ou impression CSS dédiée.
- [ ] **Skeleton loaders** : remplacer `LoadingState` générique par des squelettes par page.
- [ ] **Recherche globale admin** : palette `⌘K` (rechercher utilisateur, lot, exécution).
- [ ] **Alertes visuelles qualité faible** sur cartes admin + super-admin.
- [ ] Tests Playwright : smoke par rôle (login → dashboard → 2 navigations → logout).
- [ ] Lighthouse ≥ 90 sur `/me/dashboard` et `/admin/dashboard`.
- [ ] Seed démo + script de soutenance.

---

## 5. Conventions

### TanStack Query

- Clé = chemin d'API + filtres significatifs : `["/api/me/seances", { dateFrom, dateTo }]`.
- `staleTime: 30s` par défaut, `60s` pour les catalogues, `0` pour les pages d'audit ETL.
- Invalider après mutation par préfixe (`["/api/utilisateurs"]`).

### Formulaires

- 1 schéma Zod par form, exporté à côté du composant.
- `zodResolver`, `mode: "onBlur"`, message d'erreur via `<FormError>`.
- Toujours passer `values` (controlled) et non `defaultValues` pour les édits.

### Tables

- Toujours via `<DataTable>` + `<Pagination>` existants. Filtres au-dessus, dans `<FilterBar>` (à créer).
- Tri serveur : `sortBy` / `sortOrder` en query — extension à ajouter à `usePagedApi`.

### Charts

- Recharts uniquement. Wrappers dans `src/components/charts/` pour homogénéiser couleurs et tailles.
- Palette : `#2563eb`, `#0f766e`, `#7c3aed`, `#dc2626`, `#b54708`, `#475467` (déjà utilisée dans `me-pages.tsx`).

### Routes & permissions

- Centraliser dans `src/lib/routes.ts` : `{ path, label, roles }` par route → consommé par sidebar, breadcrumb et garde.
- `<RoleGuard roles={["ADMIN", "SUPER_ADMIN"]}>` autour de chaque layout privé (déjà présent à vérifier).

---

## 6. Risques et points de vigilance

- **Routes fantômes** : `message.txt` propose des endpoints qui n'existent pas (ex. `/api/admin/aliments` CRUD complet). À chaque sprint, **vérifier** `backend/app/modules/*.py` ; si un endpoint manque, ouvrir un ticket backend avant de builder le UI.
- **Pas de Next.js middleware d'auth** actuellement : la garde se fait côté client après hydratation. Pour la MSPR c'est suffisant ; à durcir post-MSPR (middleware → `/login` si pas de cookie refresh).
- **`apiList` dupliqué** dans `api.ts` : la logique 401/refresh est répétée. À refactoriser quand on touchera au réseau (sprint 1 ou 6).
- **Recharts + React 19** : surveiller les warnings de `findDOMNode` ; passer à v3 si bloquant.
- **Mode sombre** : Tailwind 4 utilise `@theme` ; vérifier la stratégie (`media` vs `class`) avant de coder le toggle.

---

## 7. Priorités absolues MSPR (si on coupe)

Si le temps manque, voici l'ordre de sacrifice — du plus important au moins important :

1. Login + rôles (✅ déjà OK)
2. Dashboard utilisateur (à enrichir)
3. Biométrie + sommeil (à compléter)
4. Séances + détail séance (à compléter)
5. Nutrition + détail plat (à compléter)
6. Dashboard admin
7. **Contrôle qualité + détail lot + avant/après ETL** ← **page démo clé**
8. Dashboard super admin minimal
9. Exports CSV
10. Tout le reste (référentiels CRUD, monitoring, polish)

---

## 8. Définition de "fini" par page

Pour chaque page : (1) data réelle depuis l'API, (2) loading + error states, (3) pagination/filtres si liste, (4) responsive ≥375px, (5) testée manuellement avec un seed, (6) navigable via le menu et le breadcrumb, (7) accessible (focus visible, labels). Pas de TODO commenté en prod, pas de mock laissé en place.
