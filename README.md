# Mindly

Plateforme de quiz temps réel. Le formateur crée des sessions, les participants rejoignent via un code à 6 caractères et répondent aux questions. Classement live et statistiques post-quiz.

## Stack

- **Streamlit** — interface utilisateur
- **streamlit-shadcn-ui** — composants design (shadcn/ui)
- **Redis** (Upstash) — stockage temps réel, sessions, classement
- **python-dotenv** — configuration

## Prérequis

- Python 3.12+
- Redis (ou un compte Upstash gratuit)

## Installation

```bash
git clone https://github.com/Opustic/mindly
cd mindly

python -m venv env
source env/bin/activate   # Linux / Mac / WSL
# .\env\Scripts\activate  # Windows

pip install -r requirements.txt

cp .env.example .env
```

Éditer `.env` avec votre URL Redis Upstash :

```env
REDIS_URL=rediss://default:xxxxxxxx@xxx.upstash.io:6379
FORMATEUR_PASSWORD=admin
```

## Démarrage

```bash
streamlit run app.py
```

## Utilisation

### Formateur

1. Basculer le switch **Mode Formateur** dans la sidebar
2. Entrer le mot de passe (défaut : `admin`)
3. Aller dans l'onglet **Création de Quiz**
4. Saisir le titre, les questions et les options
5. Cliquer **Sauvegarder dans Redis** — un code de session s'affiche
6. Aller dans l'onglet **Sessions Live**
7. Cliquer sur le quiz dans la liste → **Lancer le Quiz**
8. Partager le code de session avec les participants

### Participant

1. Saisir le code à 6 caractères
2. Choisir un pseudo
3. Répondre aux questions
4. Voir le score après chaque réponse

## Structures Redis

| Clé | Type | Usage |
|---|---|---|
| `quiz:<id>` | Hash | Informations du quiz |
| `quiz:<id>:questions` | List | Questions (JSON) |
| `session:<quiz>:<pseudo>` | Hash | Session d'un participant |
| `reponse:<quiz>:<q>:<pseudo>` | String | Réponse à une question |
| `classement:<quiz>` | Sorted Set | Scores des participants |
| `stats:<quiz>` | Hash | Statistiques post-quiz |
| `code:<code>` | String | Code d'accès → quiz_id |
| `quizzes:all` | Set | Index de tous les quiz |
