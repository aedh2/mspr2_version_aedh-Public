# MSPR gap analysis - HealthAI Coach

## Application web complete

Deja present:

- auth;
- espace utilisateur;
- pages nutrition, sport, sommeil, biometrie, objectifs;
- analyse repas;
- coach posture;
- admin et super-admin;
- ETL et qualite.

Manques principaux:

- historique utilisateur consolide cote backend;
- dashboard KPI calcule cote backend avec contrat stable;
- workflow complet objectifs vers recommandations;
- suivi explicite des actions IA/API pour audit MSPR;
- onboarding profil utilisateur plus complet: allergies, regime, budget, equipement, contraintes sante.

## IA/API

Deja present:

- Hugging Face pour analyse repas si `AI_ENABLE_EXTERNAL_CALLS=true`;
- DeepSeek optionnel pour feedback posture texte;
- MediaPipe cote navigateur pour detection posture;
- fallback local documente.

Manques:

- registre admin des appels IA/API avec statut, latence, fournisseur, fallback utilise;
- documentation API IA dans une page admin lisible;
- option IA externe pour enrichir les recommandations, avec moteur local conservé en fallback;
- tests d'erreur sur timeouts et indisponibilite fournisseur.

## KPI

Deja present:

- KPI utilisateur partiels: poids, IMC, sommeil, seances, calories;
- KPI admin qualite/ETL;
- graphiques sport/nutrition/sommeil.

Manques:

- readiness score calcule et stocke cote backend;
- score nutrition, activite, sommeil et regularite expose par endpoint;
- macro balance et proteines atteintes dans le journal utilisateur;
- streak officiel;
- calories moyennes sur fenetre configurable;
- KPI IA/API.

## UX

Ameliore dans cette etape:

- `/me/dashboard` ressemble davantage a une application sante;
- ajout de cartes KPI, jauges circulaires, progress bars, donut, skeletons et empty states;
- ajout de `/me/historique`;
- navigation sidebar conservee.

Restant:

- harmoniser les pages `/me/profile`, `/me/objectifs`, `/me/nutrition`, `/me/exercices` au meme niveau visuel;
- ajouter des filtres avances historiques;
- ajouter des tests d'accessibilite;
- verifier visuellement mobile/tablette via navigateur.

## Securite

Deja present:

- JWT;
- refresh token;
- roles;
- variables d'environnement pour secrets;
- pas de cle API hardcodee ajoutee.

Risques:

- `JWT_SECRET_KEY` a une valeur de fallback locale a changer en prod;
- CORS a verrouiller en prod;
- upload image repas et snapshots posture a surveiller: taille, type MIME, stockage;
- logs IA/API a purger de toute donnee sensible;
- rate limiting a confirmer sur endpoints IA.

## Tests

Presents:

- `backend/tests/test_api_contracts.py`
- `backend/tests/test_coach_posture_logic.py`
- `backend/tests/test_recommendation_rules.py`
- `healthai_etl/tests/test_etl_helpers.py`
- `frontend/src/features/coach-posture/logic.spec.ts`

Manques:

- tests frontend dashboard/historique;
- tests integration recommandations avec allergies/equipement;
- tests API IA fallback;
- tests Docker final;
- tests accessibilite et responsive.

## Docker / donnees

Manque bloquant potentiel:

- `docker-compose.yml` monte `../healthai_coaching bdd remplite.sql`, alors que le dump present est `backend/healthai_coaching bdd remplite.sql`.

Risque:

- la base MariaDB peut ne pas etre initialisee correctement en environnement neuf tant que ce chemin n'est pas corrige.
