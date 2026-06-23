Voici un livrable d’architecture complet, réaliste et directement exploitable pour développer toute la plateforme HealthAI à partir de ta base actuelle. La base supporte déjà les trois rôles UTILISATEUR, ADMIN, SUPER_ADMIN, le rattachement organisationnel, les identifiants externes gym_external_id et sleep_external_id, la traçabilité ETL (source_donnees, execution_etl, lot_donnees, enregistrement_brut, stg_import) et le contrôle qualité unifié via controle_qualite_donnee. Elle porte aussi tout le métier attendu : objectifs, biométrie, sommeil, séances, exercices, plats, journal alimentaire et photos de progression.

1. Choix d’architecture recommandé

Je te recommande une architecture en deux applications séparées.

Front-end
Tailwind CSS
shadcn/ui pour les composants
TanStack Query pour les appels API et le cache
React Hook Form + Zod pour les formulaires
ECharts ou Recharts pour les graphiques
zustand seulement pour un petit état global léger si nécessaire
Back-end
NestJS + TypeScript
Prisma sur MariaDB/MySQL existant, avec introspection de la base déjà créée
JWT access token + refresh token en cookie HttpOnly
Swagger / OpenAPI
class-validator pour les DTO
Pino ou équivalent pour les logs
Multer si plus tard tu ajoutes l’upload manuel de photos
Pourquoi ce choix
très bon rendu soutenance
structure propre par modules
bonne séparation front/back
sécurité facile à mettre en place
pagination, filtres et dashboards faciles à maintenir
bon compromis entre rapidité de dev et qualité pro
2. Vision cible du produit

L’application doit être pensée comme une plateforme orientée rôles.

Espace public
connexion
mot de passe oublié
éventuellement page d’accueil simple
Espace utilisateur
tableau de bord santé
profil
objectifs
mesures biométriques
sommeil
séances
détail séance
catalogue exercices
nutrition
détail plat
catalogue aliments
progression photo
Espace admin
dashboard métier + ETL
utilisateurs
fiche utilisateur
exécutions ETL
lots de données
détail lot
contrôle qualité
vue avant / après ETL
référentiels
exports
Espace super admin
dashboard global plateforme
organisations
sources de données
monitoring ETL global

Cette organisation colle parfaitement à ton schéma, où utilisateur est la table centrale, liée à organisation, objectif_utilisateur, mesure_biometrique, mesure_sommeil_sante, seance_entrainement, plat, journal_alimentaire et progression_photo.

3. Architecture front-end
3.1 Structure de dossiers recommandée
frontend/
  src/
    app/
      (public)/
        login/
        forgot-password/
      (user)/
        dashboard/
        profile/
        objectifs/
        biometrie/
        sommeil/
        seances/
        seances/[id]/
        exercices/
        exercices/[id]/
        nutrition/
        nutrition/plats/[id]/
        aliments/
        photos/
      (admin)/
        admin/dashboard/
        admin/utilisateurs/
        admin/utilisateurs/[id]/
        admin/etl/executions/
        admin/etl/executions/[id]/
        admin/etl/lots/
        admin/etl/lots/[id]/
        admin/qualite/
        admin/etl/compare/
        admin/aliments/
        admin/exercices/
        admin/regles-qualite/
        admin/exports/
      (super-admin)/
        super-admin/dashboard/
        super-admin/organisations/
        super-admin/organisations/[id]/
        super-admin/sources/
        super-admin/monitoring/
    components/
      ui/
      layout/
      charts/
      tables/
      filters/
      forms/
      cards/
    features/
      auth/
      dashboard/
      users/
      objectifs/
      biometrie/
      sommeil/
      seances/
      exercices/
      nutrition/
      photos/
      etl/
      qualite/
      organisations/
      sources/
      exports/
    lib/
      api/
      auth/
      utils/
      constants/
      permissions/
    hooks/
    types/
3.2 Layouts
PublicLayout
UserLayout
AdminLayout
SuperAdminLayout

Chaque layout contient :

sidebar ou top nav
breadcrumb
garde de rôle
header utilisateur connecté
zone notifications
contenu scrollable
3.3 Composants transverses

Tu vas réutiliser partout :

AppTable
AppPagination
AppFilters
StatCard
ChartCard
DateRangeFilter
StatusBadge
RoleBadge
QualityLevelBadge
DecisionBadge
EntityDrawer
ConfirmDialog
ExportButton
EmptyState
LoadingState
ErrorState
4. Architecture back-end
4.1 Structure de dossiers recommandée
backend/
  src/
    main.ts
    app.module.ts
    common/
      decorators/
      guards/
      interceptors/
      filters/
      pipes/
      dto/
      types/
      utils/
    config/
      env/
      swagger/
      auth/
    prisma/
      schema.prisma
      migrations/
    modules/
      auth/
        auth.controller.ts
        auth.service.ts
        auth.module.ts
        dto/
      users/
        users.controller.ts
        users.service.ts
        users.module.ts
        dto/
      organisations/
      objectifs/
      mesures-biometriques/
      mesures-sommeil/
      seances/
      exercices/
      aliments/
      plats/
      journal-alimentaire/
      photos/
      etl-executions/
      etl-lots/
      etl-raw/
      etl-staging/
      qualite/
      regles-qualite/
      sources/
      exports/
4.2 Pattern interne

Pour chaque module :

controller : HTTP
service : logique métier
repository ou accès Prisma : requêtes
dto : validation entrée/sortie
mapper : transformation DB → réponse API
4.3 Principes
lecture paginée partout
filtres côté serveur
tri côté serveur
agrégations calculées côté back
contrôle d’accès par rôle
contrôle d’appartenance sur les routes /me/*
5. Modélisation métier à utiliser côté code
5.1 Entités principales

À mapper depuis la base :

Utilisateur
Organisation
ObjectifUtilisateur
MesureBiometrique
MesureSommeilSante
SeanceEntrainement
SeanceExercice
Exercice
Aliment
Plat
JournalAlimentaire
ProgressionPhoto
SourceDonnees
ExecutionEtl
LotDonnees
EnregistrementBrut
StgImport
RegleQualite
ControleQualiteDonnee

La table utilisateur contient déjà le cœur de la sécurité et du profil : organisation, login, email, date de naissance, genre, taille, rôle, statut, mot de passe hashé, et les identifiants externes gym/sleep, avec unicité sur le login, l’email et ces identifiants externes.

5.2 Relations importantes à respecter
une organisation possède plusieurs utilisateurs
un utilisateur possède plusieurs objectifs
un utilisateur possède plusieurs mesures biométriques
un utilisateur possède plusieurs mesures sommeil
un utilisateur possède plusieurs séances
une séance possède plusieurs lignes seance_exercice
une ligne seance_exercice référence un exercice
un utilisateur possède plusieurs plats
un plat possède plusieurs lignes journal_alimentaire
une ligne journal_alimentaire peut référencer un aliment
un utilisateur possède plusieurs photos de progression
un lot appartient à une exécution ETL et à une source
un contrôle qualité référence une exécution, un lot et éventuellement une règle

Ces relations sont déjà matérialisées par les clés étrangères du schéma.

6. Sécurité et gestion des rôles
6.1 Rôles
UTILISATEUR
ADMIN
SUPER_ADMIN
6.2 Politique d’accès
Public
login
reset password
Utilisateur
accès uniquement à ses propres données
routes /api/me/*
Admin
accès lecture à tous les utilisateurs
gestion des lots, exécutions, qualité, référentiels
pas de gestion globale des organisations et sources sensibles
Super admin
accès total
gestion organisations
gestion sources
monitoring global
6.3 À implémenter
JwtAuthGuard
RolesGuard
décorateur @Roles(...)
décorateur @CurrentUser()
contrôle d’appartenance dans les services
6.4 Session

Je te conseille :

access token court
refresh token plus long
refresh stocké en cookie HttpOnly
déconnexion via invalidation refresh
7. Format API standard
7.1 Réponse liste paginée
{
  "data": [],
  "meta": {
    "page": 1,
    "pageSize": 20,
    "total": 245,
    "totalPages": 13
  },
  "filters": {
    "search": null,
    "sortBy": "cree_le",
    "sortOrder": "desc"
  }
}
7.2 Réponse erreur
{
  "statusCode": 400,
  "message": "Paramètres invalides",
  "errors": {
    "dateFrom": "Format invalide"
  }
}
7.3 Query params standards
page
pageSize
sortBy
sortOrder
search
dateFrom
dateTo
filtres métier selon module
8. Pages front-end à créer
8.1 Public
/login

Composants :

LoginForm
AuthCard
PasswordInput
FormError

Appels :

POST /api/auth/login
GET /api/auth/me
/forgot-password

Composants :

ForgotPasswordForm
SuccessAlert

Appels :

POST /api/auth/forgot-password
8.2 Utilisateur
/dashboard

Composants :

UserKpiCards
WeightChart
BmiChart
SleepChart
CaloriesBalanceChart
MealTypeChart
WorkoutTypeChart
RecentSessionsList
RecentMealsList
LastObjectiveCard
ProgressPhotoPreview

Appels :

GET /api/me/dashboard
GET /api/me/kpis
GET /api/me/charts/weight
GET /api/me/charts/bmi
GET /api/me/charts/sleep
GET /api/me/charts/calories-balance
GET /api/me/charts/meal-types
GET /api/me/charts/workout-types

Données :

objectifs, biométrie, sommeil, séances, plats, journal, photos
/profile

Composants :

ProfileCard
ProfileForm
ChangePasswordForm
OrganisationCard

Appels :

GET /api/me/profile
PUT /api/me/profile
PUT /api/me/password
/objectifs

Composants :

ActiveObjectiveCard
ObjectiveHistoryTimeline

Appels :

GET /api/me/objectifs
GET /api/me/objectifs/actif

La table objectif_utilisateur stocke type, dates, commentaire et statut actif logique via actif_unique.

/biometrie

Composants :

BiometrieTable
WeightChart
BmiChart
BodyFatChart
HeartRateChart
HydrationChart
DateRangeFilter

Appels :

GET /api/me/mesures-biometriques
GET /api/me/mesures-biometriques/latest
GET /api/me/mesures-biometriques/charts

La table mesure_biometrique expose déjà poids, taille, IMC, masse grasse, BPM repos/moyen/max et hydratation.

/sommeil

Composants :

SleepTable
SleepDurationChart
StressChart
StepsChart
SleepQualityChart
BloodPressureCard

Appels :

GET /api/me/sommeil
GET /api/me/sommeil/latest
GET /api/me/sommeil/charts

La table mesure_sommeil_sante contient durée, qualité, activité physique, stress, tension, fréquence cardiaque, pas et trouble du sommeil.

/seances

Composants :

SessionsTable
WorkoutTypeFilter
SessionsPerWeekChart
BurnedCaloriesChart

Appels :

GET /api/me/seances
GET /api/me/seances/kpis
GET /api/me/seances/charts

La table seance_entrainement contient date, type, durée, calories, fréquence hebdo, niveau d’expérience et eau.

/seances/[id]

Composants :

SessionHeader
SessionExercisesTable
CaloriesByExerciseChart
DurationByExerciseChart
VolumeByExerciseChart

Appels :

GET /api/me/seances/{id}
GET /api/me/seances/{id}/exercices

La relation séance → exercices passe par seance_exercice(seance_id, exercice_id, ordre_exercice, series_nb, repetitions_nb, charge_kg, duree_min, calories_brulees_estimees, commentaire).

/exercices

Composants :

ExercisesGrid
ExerciseFilters
SearchBar

Appels :

GET /api/exercices
GET /api/exercices/filters

La table exercice contient le nom, plusieurs chemins GIF, body part, muscle cible, équipement et les champs JSON d’instructions et de muscles.

/exercices/[id]

Composants :

ExerciseHero
ExerciseGifTabs
ExerciseInstructionsList
ExerciseMetaCard

Appels :

GET /api/exercices/{id}
/nutrition

Composants :

MealsTable
PlatsTable
CaloriesPerDayChart
TopFoodsChart
MealTypePieChart

Appels :

GET /api/me/plats
GET /api/me/journal-alimentaire
GET /api/me/nutrition/charts
/nutrition/plats/[id]

Composants :

PlatHeader
PlatLinesTable
CaloriesByFoodChart
PlatSummaryCard

Appels :

GET /api/me/plats/{id}
GET /api/me/plats/{id}/lignes

La table plat porte calories_totales_kcal, et journal_alimentaire porte les lignes détaillées avec plat_id, aliment_id, quantité, unité, calories et eau, ce qui permet d’afficher la somme réelle du plat.

/aliments

Composants :

FoodsTable
NutritionFilters
NutritionSortSelect

Appels :

GET /api/aliments
GET /api/aliments/{id}

La table aliment contient catégorie et valeurs nutritionnelles détaillées.

/photos

Composants :

BeforeAfterGallery
PhotoTimeline
ObjectiveLinkedBadge

Appels :

GET /api/me/photos-progression

La table progression_photo relie un utilisateur, éventuellement un objectif, un type BEFORE/AFTER/AUTRE, une image et une date.

8.3 Admin
/admin/dashboard

Composants :

AdminKpiCards
QualityBySourceChart
RejectsByLotChart
ImportsVolumeChart
UsersByOrganisationChart
TopBrokenRulesChart

Appels :

GET /api/admin/dashboard
GET /api/admin/dashboard/kpis
GET /api/admin/dashboard/charts/quality-by-source
GET /api/admin/dashboard/charts/rejects-by-lot
GET /api/admin/dashboard/charts/imports-volume
GET /api/admin/dashboard/charts/users-by-organisation
GET /api/admin/dashboard/charts/top-rules

Cette page s’appuie surtout sur utilisateur, organisation, execution_etl, lot_donnees, source_donnees et controle_qualite_donnee.

/admin/utilisateurs

Composants :

UsersTable
RoleFilter
OrganisationFilter
StatusFilter

Appels :

GET /api/admin/utilisateurs
PATCH /api/admin/utilisateurs/{id}/statut
/admin/utilisateurs/[id]

Composants :

AdminUserHeader
AdminUserTabs
ResumeTab
ObjectifsTab
BiometrieTab
SommeilTab
SeancesTab
NutritionTab
PhotosTab

Appels :

GET /api/admin/utilisateurs/{id}/resume
GET /api/admin/utilisateurs/{id}/mesures-biometriques
GET /api/admin/utilisateurs/{id}/sommeil
GET /api/admin/utilisateurs/{id}/seances
GET /api/admin/utilisateurs/{id}/plats
GET /api/admin/utilisateurs/{id}/photos
/admin/etl/executions

Composants :

ExecutionsTable
ExecutionStatusFilter
SourceFilter

Appels :

GET /api/admin/etl/executions
GET /api/admin/etl/executions/{id}

execution_etl stocke statut, démarrage, fin, lignes lues/valides/invalides, doublons, corrections, rejets et taux qualité.

/admin/etl/lots

Composants :

LotsTable
LotStatusFilter
LotValidationActions

Appels :

GET /api/admin/etl/lots
GET /api/admin/etl/lots/{id}
PATCH /api/admin/etl/lots/{id}/statut

lot_donnees relie un lot à une exécution, une source, un créateur, un validateur et un statut de workflow.

/admin/etl/lots/[id]

Composants :

LotSummaryCard
RawDataTable
StagingTable
QualityControlsTable
GeneratedDataImpactCards

Appels :

GET /api/admin/etl/lots/{id}/resume
GET /api/admin/etl/lots/{id}/raw
GET /api/admin/etl/lots/{id}/staging
GET /api/admin/etl/lots/{id}/controles
GET /api/admin/etl/lots/{id}/impacts

enregistrement_brut garde le payload d’origine et stg_import garde le payload normalisé avec parseabilité et statut de validation.

/admin/qualite

Composants :

QualityControlsTable
QualityFilters
QualityKpiCards
QualityTimelineChart
TopFieldsChart
TopRulesChart
QualityBySourceChart
QualityByLotChart

Appels :

GET /api/admin/qualite/controles
GET /api/admin/qualite/controles/{id}
GET /api/admin/qualite/kpis
GET /api/admin/qualite/charts/levels
GET /api/admin/qualite/charts/decisions
GET /api/admin/qualite/charts/top-rules
GET /api/admin/qualite/charts/top-fields
GET /api/admin/qualite/charts/by-source
GET /api/admin/qualite/charts/by-lot
GET /api/admin/qualite/charts/timeline

La table controle_qualite_donnee permet déjà exactement ce type de vue avec niveau, type_controle, decision_finale, code_controle, description, etape_pipeline, ref_externe et payload_json.

/admin/etl/compare

Composants :

BeforeAfterViewer
RawPayloadViewer
NormalizedPayloadViewer
QualityDecisionPanel

Appels :

GET /api/admin/etl/compare?lotId=&entite=&refExterne=
/admin/aliments
référentiel aliment
CRUD simple contrôlé
/admin/exercices
consultation du catalogue d’exercices
correction éventuelle des métadonnées
/admin/regles-qualite
gestion des règles
activation / désactivation
/admin/exports
export CSV
export Excel
export PDF synthèse
8.4 Super admin
/super-admin/dashboard

Composants :

GlobalKpiCards
QualityByOrganisationChart
VolumesBySourceChart
GlobalHeatmap

Appels :

GET /api/super-admin/dashboard
/super-admin/organisations

Composants :

OrganisationsTable
OrganisationForm
OrganisationStatsPanel

Appels :

GET /api/super-admin/organisations
GET /api/super-admin/organisations/{id}
POST /api/super-admin/organisations
PUT /api/super-admin/organisations/{id}
/super-admin/sources

Composants :

SourcesTable
SourceStatusToggle
SourceStatsCard

Appels :

GET /api/super-admin/sources
PUT /api/super-admin/sources/{id}
/super-admin/monitoring

Composants :

FailedExecutionsTable
BlockedLotsTable
AbnormalRejectRateChart

Appels :

GET /api/super-admin/monitoring/etl
GET /api/super-admin/monitoring/qualite
9. Endpoints back-end à implémenter
9.1 AuthController
POST /api/auth/login
POST /api/auth/logout
GET /api/auth/me
POST /api/auth/forgot-password
POST /api/auth/reset-password
9.2 MeController
GET /api/me/dashboard
GET /api/me/kpis
GET /api/me/profile
PUT /api/me/profile
PUT /api/me/password
GET /api/me/objectifs
GET /api/me/objectifs/actif
GET /api/me/mesures-biometriques
GET /api/me/mesures-biometriques/latest
GET /api/me/mesures-biometriques/charts
GET /api/me/sommeil
GET /api/me/sommeil/latest
GET /api/me/sommeil/charts
GET /api/me/seances
GET /api/me/seances/{id}
GET /api/me/seances/{id}/exercices
GET /api/me/plats
GET /api/me/plats/{id}
GET /api/me/plats/{id}/lignes
GET /api/me/journal-alimentaire
GET /api/me/nutrition/charts
GET /api/me/photos-progression
9.3 ExercicesController
GET /api/exercices
GET /api/exercices/{id}
GET /api/exercices/filters
9.4 AlimentsController
GET /api/aliments
GET /api/aliments/{id}
9.5 AdminUsersController
GET /api/admin/utilisateurs
GET /api/admin/utilisateurs/{id}
PUT /api/admin/utilisateurs/{id}
PATCH /api/admin/utilisateurs/{id}/statut
9.6 AdminEtlExecutionsController
GET /api/admin/etl/executions
GET /api/admin/etl/executions/{id}
9.7 AdminEtlLotsController
GET /api/admin/etl/lots
GET /api/admin/etl/lots/{id}
PATCH /api/admin/etl/lots/{id}/statut
GET /api/admin/etl/lots/{id}/resume
GET /api/admin/etl/lots/{id}/raw
GET /api/admin/etl/lots/{id}/staging
GET /api/admin/etl/lots/{id}/controles
GET /api/admin/etl/lots/{id}/impacts
GET /api/admin/etl/compare
9.8 AdminQualiteController
GET /api/admin/qualite/controles
GET /api/admin/qualite/controles/{id}
GET /api/admin/qualite/kpis
GET /api/admin/qualite/charts/levels
GET /api/admin/qualite/charts/decisions
GET /api/admin/qualite/charts/top-rules
GET /api/admin/qualite/charts/top-fields
GET /api/admin/qualite/charts/by-source
GET /api/admin/qualite/charts/by-lot
GET /api/admin/qualite/charts/timeline
9.9 AdminReferentielsController
GET /api/admin/aliments
POST /api/admin/aliments
PUT /api/admin/aliments/{id}
DELETE /api/admin/aliments/{id}
GET /api/admin/exercices
PUT /api/admin/exercices/{id}
GET /api/admin/regles-qualite
GET /api/admin/regles-qualite/{id}
PUT /api/admin/regles-qualite/{id}
9.10 AdminExportsController
GET /api/admin/exports/utilisateurs
GET /api/admin/exports/nutrition
GET /api/admin/exports/sport
GET /api/admin/exports/sommeil
GET /api/admin/exports/qualite
9.11 SuperAdminController
GET /api/super-admin/dashboard
GET /api/super-admin/organisations
GET /api/super-admin/organisations/{id}
POST /api/super-admin/organisations
PUT /api/super-admin/organisations/{id}
GET /api/super-admin/sources
PUT /api/super-admin/sources/{id}
GET /api/super-admin/monitoring/etl
GET /api/super-admin/monitoring/qualite
10. Services à prévoir
AuthService
validation identifiants
génération tokens
refresh
logout
reset password
UsersService
profil courant
liste admin
fiche utilisateur complète
changement statut
DashboardService
agrégations par rôle
KPI utilisateur
KPI admin
KPI super admin
ObjectifsService
objectif actif
historique
comparaison progression / objectif
BiometrieService
séries temporelles
latest value
calculs dérivés
SommeilService
séries temporelles
résumé santé sommeil
SeancesService
liste séances
détail séance
agrégats calories/durée
top exercices
ExercicesService
catalogue
filtres
détail complet
NutritionService
plats
journal alimentaire
calories par jour
top aliments
détail plat avec somme
PhotosService
galerie
couple before/after
liaison objectif
EtlExecutionsService
liste
détail
suivi statuts
EtlLotsService
workflow lot
détail lot
données raw/staging/finales
QualiteService
liste contrôles
KPI qualité
top règles
top champs
timeline
qualité par source et lot
ReferentielsService
aliments
exercices
règles qualité
ExportsService
CSV
Excel
PDF
11. Contrôleurs et logique SQL par module
11.1 Utilisateurs

Requêtes basées sur :

utilisateur
jointure organisation
filtres role, statut, organisation_id
gym_external_id, sleep_external_id pour la traçabilité simplifiée
11.2 Dashboard utilisateur

Agrégations :

dernier objectif actif depuis objectif_utilisateur
dernière biométrie via mesure_biometrique
dernier sommeil via mesure_sommeil_sante
stats séances via seance_entrainement
stats plats / journal via plat et journal_alimentaire
photo récente via progression_photo
11.3 Détail séance

Jointure :

seance_entrainement
seance_exercice
exercice
11.4 Détail plat

Jointure :

plat
journal_alimentaire
aliment
et contrôle que plat.calories_totales_kcal = somme des lignes retournées.
11.5 Détail lot

Jointure :

lot_donnees
execution_etl
source_donnees
enregistrement_brut
stg_import
controle_qualite_donnee
12. Pagination, tri, filtres
12.1 Pagination obligatoire sur
utilisateurs
séances
exercices
aliments
journal alimentaire
plats
exécutions ETL
lots
contrôles qualité
données raw
données staging
12.2 Filtres principaux
Utilisateur
rôle
statut
organisation
recherche email/pseudo
Séances
dateFrom/dateTo
type entraînement
calories min/max
Nutrition
dateFrom/dateTo
type repas
utilisateur
aliment
ETL
source
statut
date
lot
Qualité
niveau
type contrôle
décision finale
entité
lot
source
champ
règle
étape pipeline
12.3 Tri standards
cree_le desc
date_seance desc
mesure_le desc
consomme_le desc
13. Dashboards et graphiques
13.1 Dashboard utilisateur
poids dans le temps
IMC
sommeil
calories consommées vs brûlées
répartition repas
répartition entraînements
top exercices
top aliments
bloc objectif actif
bloc photo progression
13.2 Dashboard admin
nb utilisateurs
nb séances
nb plats
nb mesures
nb exécutions ETL
taux qualité global
rejets par lot
qualité par source
top règles cassées
top entités en erreur
volumes importés
13.3 Dashboard super admin
qualité par organisation
volumes par organisation
volumes par source
heatmap anomalies par jour
source la plus problématique
organisation la plus active

controle_qualite_donnee a été conçue précisément pour supporter ces vues avec des filtres par niveau, type, décision et étape pipeline.

14. Exports
14.1 Formats
CSV pour les tableaux
Excel pour les exports analytiques
PDF pour les synthèses
14.2 Exports à prévoir
utilisateurs
biométrie
sommeil
séances
nutrition
qualité ETL
exécutions
lots
14.3 Bon pattern
endpoint qui génère le fichier
lien signé ou réponse stream
historique d’exports plus tard en bonus
15. Logique ETL / qualité à exploiter dans l’application

Le pipeline narratif à montrer dans la soutenance est :

source externe
enregistrement brut
staging normalisé
contrôle qualité
chargement dans les tables métier

C’est exactement ce que permet ton schéma avec source_donnees, execution_etl, lot_donnees, enregistrement_brut, stg_import, regle_qualite, controle_qualite_donnee puis les tables métier finales.

15.1 Pages ETL les plus importantes
liste exécutions
détail exécution
liste lots
détail lot
contrôle qualité
avant / après ETL
15.2 Ce qu’il faut afficher dans “Avant / Après”
payload brut
payload normalisé
règle qualité impliquée
niveau
décision finale
valeur observée
valeur corrigée si applicable
16. Dossiers de code concrets par module backend
Exemple pour seances
modules/seances/
  seances.module.ts
  seances.controller.ts
  seances.service.ts
  dto/
    get-seances.query.dto.ts
    get-seance-by-id.param.dto.ts
  mappers/
    seance.mapper.ts
Exemple pour qualite
modules/qualite/
  qualite.module.ts
  qualite.controller.ts
  qualite.service.ts
  dto/
    get-quality-controls.query.dto.ts
    get-quality-kpis.query.dto.ts
  queries/
    quality-aggregations.sql.ts
17. Stratégie de développement conseillée
Sprint 1 — Socle technique
init front
init back
connexion DB
auth
rôles
layouts
menu selon rôle
swagger
pattern pagination/filtres commun
Sprint 2 — Espace utilisateur
profile
dashboard
objectifs
biométrie
sommeil
Sprint 3 — Sport + nutrition
séances
détail séance
catalogue exercices
aliments
plats
journal alimentaire
détail plat
photos progression
Sprint 4 — Admin ETL / qualité
dashboard admin
exécutions ETL
lots
détail lot
contrôle qualité
vue avant / après
Sprint 5 — Super admin + exports
dashboard global
organisations
sources
monitoring
exports
Sprint 6 — Finition MSPR
tests
polish UI
seed de démo
capture vidéo
script de soutenance
18. Priorités absolues pour la MSPR

Pour un rendu fort, je te conseille de sécuriser en priorité :

connexion + rôles
dashboard utilisateur
biométrie
sommeil
séances + détail séance
nutrition + détail plat
dashboard admin
contrôle qualité
détail lot
vue avant / après ETL
dashboard super admin simple
19. Bonus intelligents

Les bonus qui donnent une impression très pro :

mode sombre
export PDF dashboard utilisateur
favoris ou raccourcis admin
drill-down depuis un KPI vers la liste filtrée
comparaison de périodes
indicateurs de tendance
alertes visuelles sur qualité faible
skeleton loaders
recherche globale admin
20. Conclusion

La meilleure solution pour ton projet est :

front Next.js structuré par rôle
back NestJS modulaire
REST paginé, filtrable, sécurisé
dashboards métier + ETL
lecture forte de la traçabilité des données

Et surtout, ta base actuelle est déjà parfaitement adaptée à ce plan, car elle combine :

un noyau utilisateur/organisation sécurisé
des tables métier claires pour sport, nutrition, sommeil et objectifs
une traçabilité ETL complète
une table qualité unifiée pensée pour le monitoring admin

Je peux maintenant te faire l’étape suivante la plus utile : le blueprint technique exact du projet NestJS + Next.js avec arborescence finale, DTOs, noms de fichiers, routes front et squelettes de contrôleurs à copier-coller.
