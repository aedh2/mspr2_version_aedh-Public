# AI Setup

## Objectif

Cette fonctionnalite active une vraie reconnaissance d'image pour `/me/analyse-plat` via Hugging Face, avec le modele `nateraw/food`, puis mappe les labels retournes vers la table locale `aliment` pour estimer calories et macronutriments.

## 1. Creer un token Hugging Face

1. Creez un compte sur `https://huggingface.co/`
2. Ouvrez `Settings > Access Tokens`
3. Creez un token fin avec permission Inference Providers / serverless inference
4. Ne committez jamais ce token dans le code

Si un token a deja ete partage dans un message ou un historique, revoquez-le et creez-en un nouveau avant utilisation.

## 2. Variables a remplir dans `.env`

Ajoutez ou mettez a jour :

```env
AI_ENABLE_EXTERNAL_CALLS=true
MEAL_AI_FORCE_MOCK=false
HF_TOKEN=ton_nouveau_token_huggingface
HUGGINGFACE_API_TOKEN=ton_nouveau_token_huggingface
HUGGINGFACE_VISION_MODEL=nateraw/food
```

Notes :

- `HF_TOKEN` est prioritaire si les deux sont renseignes
- `HUGGINGFACE_API_TOKEN` est un fallback
- si aucun token n'est fourni, l'application reste en `local_mock`

## 3. Modele utilise

- Modele Hugging Face : `nateraw/food`
- Tache : `image-classification`
- Le modele retourne des labels du type `pizza`, `omelette`, `fried_rice`, etc.

## 4. Activer l'analyse reelle

Pour sortir du mode demo :

```env
AI_ENABLE_EXTERNAL_CALLS=true
MEAL_AI_FORCE_MOCK=false
```

Ensuite relancez les conteneurs concernes :

```bash
docker compose up -d --build backend frontend
```

## 5. Tester la route de config

URL :

```text
http://localhost:8000/api/me/analyse-plat/config
```

La route retourne uniquement l'etat de configuration, jamais le token :

```json
{
  "data": {
    "external_ai_enabled": true,
    "huggingface_configured": true,
    "vision_model": "nateraw/food",
    "force_mock": false
  }
}
```

## 6. Tester l'analyse avec une image

1. Ouvrez `http://localhost:3000/me/analyse-plat`
2. Prenez une photo ou importez une image
3. Cliquez sur `Analyser le plat`
4. Verifiez :
   - la provenance de l'analyse
   - les labels bruts Hugging Face
   - les correspondances dans la base locale `aliment`
   - les calories et macros estimees

## 7. Limites connues

- `nateraw/food` est base sur Food-101, donc certains plats proches peuvent etre confondus
- les portions sont des portions standards, pas des mesures exactes
- une photo unique ne montre pas toujours sauces, huiles, ingredients caches ou quantites reelles
- si aucun aliment n'est trouve dans la base locale, l'application retombe sur une estimation de profil standard sans planter

## Coach posture

### Role du module

La page `/me/coach-posture` fournit un coach visuel pour cinq exercices visibles : squat, curl biceps, gainage, chaise contre mur et posture de l'arbre. Jumping jack et pompes ont ete retires de la liste visible. Le frontend gere la camera, MediaPipe, le canvas, le squelette courant, le guide cible, le statut de posture, les Reps, les Sets et les chronos statiques.

### Pourquoi la pose est cote frontend

MediaPipe `PoseLandmarker` detecte le squelette reel directement dans le navigateur avec `@mediapipe/tasks-vision`. MediaPipe `HandLandmarker` est aussi utilise, quand il charge correctement, pour afficher le squelette de la main et detecter trois gestes : "OK" pour lancer l'analyse, "peace" pour capturer une photo, et "pause" pour figer/reprendre la seance. La detection main est independante de la detection corps : une main visible peut declencher OK, pause ou photo meme si la posture corps est momentanement perdue. Les frames camera ne sont pas envoyees au backend. Le backend ne recoit qu'un resume non sensible : exercice, statut, angles, erreurs detectees, Reps, Reps du set courant, Sets, chrono, meilleur temps, temps valides, score d'alignement et etat de detection personne.

Le module frontend expose `createPoseDetector()`. Le mode par defaut est `mediapipe`. Si le modele, les fichiers WASM ou le navigateur ne permettent pas de charger MediaPipe, la page bascule en `simulation` et affiche clairement ce mode.

### Exercices dynamiques et statiques

Les exercices dynamiques visibles (`squat`, `curl_biceps`) utilisent une machine d'etat :

1. phase basse ou fermee (`phase_initiale`)
2. phase haute ou ouverte (`phase_contractee`)
3. retour a la phase initiale

Une Rep est comptee uniquement apres un cycle complet. Les Sets representent les series : quand `repsInCurrentSet` atteint `targetRepsPerSet`, `sets` augmente de 1 et `repsInCurrentSet` revient a 0.

Les exercices statiques (`gainage`, `wall_sit`, `tree_pose`) n'utilisent pas les repetitions. Leur chrono avance seulement si une personne est detectee, si les landmarks requis sont presents, si le statut est `correct` et si le score atteint le seuil correct. Le chrono se met en pause en `almost`, `incorrect`, detection partielle ou perte de personne. Le bouton `Valider le temps` enregistre un temps local pour la serie statique, conserve le meilleur temps, augmente le nombre de series validees et remet le chrono courant a 0 pour repartir proprement.

### Validation en base et historique local

Le bouton `Valider l'exercice` envoie un resume vers `POST /api/me/coach-posture/validate`. Le backend cree la table dediee `coach_posture_session` si elle n'existe pas encore, puis y enregistre la validation rattachee a l'utilisateur connecte. Cette table evite les contraintes sport generiques de `seance_entrainement` / `seance_exercice` pour les donnees propres au coach posture.

L'historique sous la camera affiche les validations recentes : heure, exercice, type, Reps, Sets, chrono, score, statut et badge enregistre. La page ajoute immediatement la validation reussie localement et recharge aussi `/api/me/coach-posture/history` pour retrouver les dernieres validations stockees en base.

Limite de stockage : le snapshot photo peut etre envoye dans le payload et reste exploitable cote frontend pour l'historique immediat. Le stockage fichier persistant des snapshots peut etre ajoute ensuite via `snapshot_path`.

### Gestes main

Quand MediaPipe Hands est disponible, tenir un signe "OK" stable environ 700 ms declenche la meme action que `Analyser ma posture`. Le geste pause utilise le signe I love you / Spider-Man : pouce ouvert, index leve, auriculaire leve, majeur et annulaire replies; s'il reste stable environ 550 ms, la session bascule pause/reprise. Le signe peace capture une photo apres environ 700 ms : index et majeur leves, annulaire et auriculaire replies, pouce plutot replie ou non dominant. Des cooldowns evitent les appels repetes. Si la detection main echoue ou si le geste est ambigu, les boutons manuels restent la voie fiable.

En pause, le chrono, les Reps et les Sets ne progressent pas. Le squelette de la main peut rester visible pour confirmer le geste, mais le guide cible est masque afin de montrer que l'analyse temps reel est figee. La main passe brievement en orange lors d'un geste reconnu, puis revient au bleu/cyan.

Le bloc camera dispose aussi d'un bouton `Plein ecran` base sur l'API fullscreen du navigateur. En plein ecran, la video, le canvas, le HUD et les squelettes restent dans le meme bloc; `Echap` permet de quitter le mode.

### Conservation d'etat par exercice

Le frontend garde une session locale par exercice :

```text
exerciseSessions = {
  squat: { reps, repsInCurrentSet, sets, holdSeconds, bestHoldSeconds, validatedHolds, phase, lastRepAt },
  curl_biceps: { ... },
  gainage: { ... },
  wall_sit: { ... },
  tree_pose: { ... }
}
```

Changer d'exercice ne remet pas les compteurs a zero. En revenant sur un exercice, on retrouve ses Reps, Sets, chrono et temps valides. Deux actions existent : reinitialiser uniquement l'exercice courant ou tout reinitialiser.

### Role de DeepSeek

DeepSeek ne detecte jamais le squelette. Si `AI_ENABLE_EXTERNAL_CALLS=true` et `DEEPSEEK_API_KEY` est renseigne, le backend peut enrichir le feedback texte a partir du resume calcule cote frontend. Si DeepSeek est absent ou echoue, le service retourne un feedback local.

Variables utiles :

```env
AI_ENABLE_EXTERNAL_CALLS=true
DEEPSEEK_API_KEY=ton_token_deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

### Comment tester

1. Ouvrir `http://localhost:3000/me/coach-posture`
2. Choisir `Curl biceps`, demarrer la camera et verifier qu'un curl complet ajoute +1 a Reps, pas aux Sets directement
3. Atteindre l'objectif de Reps du set et verifier que Sets augmente ensuite
4. Choisir `Gainage`, `Chaise contre mur` puis `Posture de l'arbre` et verifier que le chrono avance seulement en posture correcte
6. Sortir du cadre : la detection doit afficher `Aucune personne detectee` et les compteurs doivent rester stables
7. Changer d'exercice puis revenir : les compteurs et chronos precedents doivent etre conserves
8. Cliquer sur `Valider l'exercice` et verifier l'historique sous la camera
9. Faire un geste main `OK` stable pour declencher `Analyser ma posture`
10. Faire le signe I love you / Spider-Man stable pour figer puis reprendre la seance
11. Faire un signe peace stable pour capturer une photo

### Limites actuelles

- Le squelette cible est un guide visuel simplifie, pas une analyse biomecanique clinique
- Le mode simulation reste disponible comme fallback si MediaPipe ne charge pas
- Les angles dependent de la qualite camera, du cadrage et de la visibilite du corps entier
- Une camera trop basse ou trop proche peut fausser les angles
- La posture de l'arbre demande un cadrage debout complet et peut etre moins fiable si le pied leve est masque
- La lumiere faible, les vetements amples, les mouvements rapides ou les membres caches diminuent la precision
- Les gestes OK, pause et peace peuvent etre rates si la main est floue, trop proche de la camera ou partiellement cachee
- Les occlusions et sorties de cadre peuvent provoquer une detection partielle ou une pause des compteurs
- Le feedback est informatif et ne remplace pas un avis medical ou sportif personnalise
