"""
database.py
============
Toute la logique d'accès à Redis pour QuizLive.

Ce module est le SEUL point d'accès à Redis dans le projet.
Les vues Streamlit (Formateur / Participant) doivent uniquement appeler
les fonctions publiques ci-dessous, jamais interroger Redis directement.

Structures de données Redis utilisées (imposées par le sujet) :
    quiz:<quiz_id>                              -> Hash
    quiz:<quiz_id>:questions                    -> List (JSON par question)
    session:<quiz_id>:<pseudo>                  -> Hash, TTL=7200
    reponse:<quiz_id>:<q_idx>:<pseudo>           -> String, TTL variable
    classement:<quiz_id>                        -> Sorted Set
    stats:<quiz_id>                              -> Hash, TTL=604800
    code:<code>                                  -> String (quiz_id), TTL variable

Structures internes additionnelles (non imposées, ajoutées pour simplifier
le calcul du taux de bonnes réponses par question) :
    quiz:<quiz_id>:stats_q:<q_idx>               -> Hash { total, corrects }
    quizzes:all                                  -> Set (liste des quiz_id créés)
"""

import os
import json
import random
import string
import uuid
from datetime import datetime, timezone
from typing import Optional

import redis
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Connexion
# ---------------------------------------------------------------------------

STATUT_BROUILLON = "brouillon"
STATUT_ACTIF = "actif"
STATUT_TERMINE = "termine"

SESSION_TTL_SECONDES = 7200          # 2 heures
STATS_TTL_SECONDES = 604800          # 7 jours
DELTA_TTL_REPONSE = 30               # marge ajoutée au TTL d'une réponse
DELTA_TTL_CODE = 3600                # marge ajoutée au TTL du code d'accès

_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Retourne un client Redis singleton connecté via REDIS_URL (Upstash)."""
    global _client
    if _client is None:
        redis_url = os.environ.get("REDIS_URL")
        if not redis_url:
            raise RuntimeError(
                "La variable d'environnement REDIS_URL n'est pas définie. "
                "Vérifie ton fichier .env (voir .env.example)."
            )
        _client = redis.from_url(redis_url, decode_responses=True)
    return _client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Fonctionnalité 1 : Gestion des quiz
# ---------------------------------------------------------------------------

def _generate_quiz_id() -> str:
    return uuid.uuid4().hex[:12]


def _generate_unique_code(r: redis.Redis, length: int = 6) -> str:
    """Génère un code alphanumérique unique (6 caractères) non déjà utilisé."""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(alphabet, k=length))
        if not r.exists(f"code:{code}"):
            return code


def create_quiz(titre: str, duree_par_question_secondes: int, questions: list[dict]) -> dict:
    """
    Crée un nouveau quiz avec ses questions.

    questions : liste de dicts au format
        {"texte": str, "choix": [str, ...], "bonne_reponse": int}
    (entre 3 et 20 questions)

    Retourne {"quiz_id": str, "code": str}
    """
    if not (3 <= len(questions) <= 20):
        raise ValueError("Un quiz doit contenir entre 3 et 20 questions.")

    for q in questions:
        if "texte" not in q or "choix" not in q or "bonne_reponse" not in q:
            raise ValueError("Chaque question doit contenir texte, choix, bonne_reponse.")
        if not (0 <= q["bonne_reponse"] < len(q["choix"])):
            raise ValueError("bonne_reponse doit être un index valide de la liste choix.")

    r = get_redis_client()
    quiz_id = _generate_quiz_id()
    code = _generate_unique_code(r)

    quiz_key = f"quiz:{quiz_id}"
    r.hset(quiz_key, mapping={
        "titre": titre,
        "code": code,
        "statut": STATUT_BROUILLON,
        "duree_par_question_secondes": duree_par_question_secondes,
        "date_creation": _now_iso(),
        "nb_questions": len(questions),
    })

    questions_key = f"quiz:{quiz_id}:questions"
    r.delete(questions_key)  # sécurité si jamais réutilisé
    for q in questions:
        r.rpush(questions_key, json.dumps(q, ensure_ascii=False))

    # durée totale estimée du quiz, utilisée pour le TTL du code d'accès
    duree_totale = len(questions) * duree_par_question_secondes
    r.set(f"code:{code}", quiz_id, ex=duree_totale + DELTA_TTL_CODE)

    r.sadd("quizzes:all", quiz_id)

    return {"quiz_id": quiz_id, "code": code}


def get_quiz(quiz_id: str) -> Optional[dict]:
    """Retourne les infos du quiz (Hash) + questions parsées, ou None si inexistant."""
    r = get_redis_client()
    data = r.hgetall(f"quiz:{quiz_id}")
    if not data:
        return None
    data["quiz_id"] = quiz_id
    data["questions"] = get_questions(quiz_id)
    return data


def get_questions(quiz_id: str) -> list[dict]:
    """Retourne la liste des questions (dicts) d'un quiz, dans l'ordre."""
    r = get_redis_client()
    raw = r.lrange(f"quiz:{quiz_id}:questions", 0, -1)
    return [json.loads(item) for item in raw]


def get_question(quiz_id: str, q_idx: int) -> Optional[dict]:
    """Retourne une question précise par son index (0-based)."""
    r = get_redis_client()
    raw = r.lindex(f"quiz:{quiz_id}:questions", q_idx)
    return json.loads(raw) if raw else None


def start_quiz(quiz_id: str) -> None:
    """Passe le quiz au statut 'actif'."""
    r = get_redis_client()
    if not r.exists(f"quiz:{quiz_id}"):
        raise ValueError("Quiz introuvable.")
    r.hset(f"quiz:{quiz_id}", mapping={
        "statut": STATUT_ACTIF,
        "date_debut": _now_iso(),
    })


def stop_quiz(quiz_id: str) -> None:
    """Passe le quiz au statut 'termine'."""
    r = get_redis_client()
    if not r.exists(f"quiz:{quiz_id}"):
        raise ValueError("Quiz introuvable.")
    r.hset(f"quiz:{quiz_id}", mapping={
        "statut": STATUT_TERMINE,
        "date_fin": _now_iso(),
    })


def get_quiz_id_from_code(code: str) -> Optional[str]:
    """Résout un code d'accès (6 caractères) en quiz_id. None si expiré/inconnu."""
    r = get_redis_client()
    return r.get(f"code:{code}")


def get_quiz_code(quiz_id: str) -> Optional[str]:
    """Retourne le code d'accès (6 caractères) d'un quiz.

    Fonctionne pour les quiz récents (champ 'code' dans le hash)
    comme pour les anciens quiz (scan des clés code:*).
    """
    r = get_redis_client()
    data = r.hgetall(f"quiz:{quiz_id}")
    if not data:
        return None
    code = data.get("code")
    if code:
        return code
    for key in r.scan_iter(match="code:*"):
        if r.get(key) == quiz_id:
            return key.split(":", 1)[1]
    return None


def list_all_quizzes() -> list[dict]:
    """Utilitaire pour la vue Formateur : liste tous les quiz créés (encore en mémoire Redis)."""
    r = get_redis_client()
    quiz_ids = r.smembers("quizzes:all")
    quizzes = []
    for qid in quiz_ids:
        q = get_quiz(qid)
        if q:  # le hash peut avoir disparu si TTL expiré ailleurs
            quizzes.append(q)
    return quizzes


# ---------------------------------------------------------------------------
# Fonctionnalité 2 : Participation des étudiants
# ---------------------------------------------------------------------------

def join_quiz(quiz_id: str, pseudo: str) -> dict:
    """
    Inscrit un participant à un quiz actif. Si le pseudo a déjà une session
    (reconnexion), on la retourne telle quelle sans réinitialiser le score.
    """
    r = get_redis_client()
    quiz = r.hgetall(f"quiz:{quiz_id}")
    if not quiz:
        raise ValueError("Quiz introuvable.")
    if quiz.get("statut") != STATUT_ACTIF:
        raise ValueError("Ce quiz n'est pas actif, impossible de le rejoindre.")

    session_key = f"session:{quiz_id}:{pseudo}"
    existing = r.hgetall(session_key)
    if existing:
        r.expire(session_key, SESSION_TTL_SECONDES)  # renouvelle le TTL
        return existing

    r.hset(session_key, mapping={
        "pseudo": pseudo,
        "score": 0,
        "nb_bonnes_reponses": 0,
        "nb_reponses_total": 0,
    })
    r.expire(session_key, SESSION_TTL_SECONDES)

    # NX : n'écrase pas un score existant dans le classement
    r.zadd(f"classement:{quiz_id}", {pseudo: 0}, nx=True)

    return r.hgetall(session_key)


def get_session(quiz_id: str, pseudo: str) -> Optional[dict]:
    """Retourne la session d'un participant, ou None si expirée/inexistante."""
    r = get_redis_client()
    data = r.hgetall(f"session:{quiz_id}:{pseudo}")
    return data or None


def has_answered(quiz_id: str, q_idx: int, pseudo: str) -> bool:
    """Vérifie si un participant a déjà répondu à une question donnée."""
    r = get_redis_client()
    return r.exists(f"reponse:{quiz_id}:{q_idx}:{pseudo}") == 1


def _calculer_points(temps_restant_secondes: float, duree_totale_secondes: int) -> int:
    """
    Barème de points : 100 points de base pour une bonne réponse,
    + jusqu'à 50 points bonus selon la rapidité de la réponse.
    """
    base = 100
    if duree_totale_secondes <= 0:
        return base
    ratio = max(0.0, min(1.0, temps_restant_secondes / duree_totale_secondes))
    bonus = int(50 * ratio)
    return base + bonus


def submit_answer(quiz_id: str, q_idx: int, pseudo: str, reponse_idx: int,
                   temps_restant_secondes: float) -> dict:
    """
    Enregistre la réponse d'un participant à une question.

    Retourne : {"accepte": bool, "correct": bool, "points_gagnes": int,
                "score_total": int, "raison": str|None}
    """
    r = get_redis_client()

    quiz = r.hgetall(f"quiz:{quiz_id}")
    if not quiz:
        return {"accepte": False, "raison": "quiz_introuvable"}

    session_key = f"session:{quiz_id}:{pseudo}"
    if not r.exists(session_key):
        return {"accepte": False, "raison": "session_introuvable"}

    if temps_restant_secondes <= 0:
        return {"accepte": False, "raison": "temps_ecoule"}

    if has_answered(quiz_id, q_idx, pseudo):
        return {"accepte": False, "raison": "deja_repondu"}

    question = get_question(quiz_id, q_idx)
    if question is None:
        return {"accepte": False, "raison": "question_introuvable"}

    duree = int(quiz.get("duree_par_question_secondes", 0))
    reponse_key = f"reponse:{quiz_id}:{q_idx}:{pseudo}"
    r.set(reponse_key, reponse_idx, ex=duree + DELTA_TTL_REPONSE)

    correct = int(reponse_idx) == int(question["bonne_reponse"])
    points = _calculer_points(temps_restant_secondes, duree) if correct else 0

    r.hincrby(session_key, "nb_reponses_total", 1)
    stats_q_key = f"quiz:{quiz_id}:stats_q:{q_idx}"
    r.hincrby(stats_q_key, "total", 1)

    if correct:
        r.hincrby(session_key, "nb_bonnes_reponses", 1)
        r.hincrby(session_key, "score", points)
        r.zincrby(f"classement:{quiz_id}", points, pseudo)
        r.hincrby(stats_q_key, "corrects", 1)

    score_total = int(r.hget(session_key, "score") or 0)

    return {
        "accepte": True,
        "correct": correct,
        "points_gagnes": points,
        "score_total": score_total,
        "raison": None,
    }


# ---------------------------------------------------------------------------
# Fonctionnalité 3 : Classement temps réel
# ---------------------------------------------------------------------------

def get_classement(quiz_id: str, top_n: Optional[int] = None) -> list[dict]:
    """
    Retourne le classement trié par score décroissant :
    [{"pseudo": str, "score": int, "rang": int}, ...]
    """
    r = get_redis_client()
    end = (top_n - 1) if top_n else -1
    raw = r.zrevrange(f"classement:{quiz_id}", 0, end, withscores=True)
    return [
        {"pseudo": pseudo, "score": int(score), "rang": i + 1}
        for i, (pseudo, score) in enumerate(raw)
    ]


def get_taux_bonnes_reponses(quiz_id: str, q_idx: int) -> float:
    """Retourne le pourcentage de bonnes réponses pour une question (0-100)."""
    r = get_redis_client()
    stats = r.hgetall(f"quiz:{quiz_id}:stats_q:{q_idx}")
    total = int(stats.get("total", 0))
    corrects = int(stats.get("corrects", 0))
    if total == 0:
        return 0.0
    return round(corrects / total * 100, 1)


# ---------------------------------------------------------------------------
# Fonctionnalité 4 : Statistiques post-quiz
# ---------------------------------------------------------------------------

def compute_and_store_stats(quiz_id: str) -> dict:
    """
    Calcule les statistiques finales d'un quiz terminé, les stocke dans
    stats:<quiz_id> (TTL 7 jours) et les retourne.
    """
    r = get_redis_client()
    quiz = get_quiz(quiz_id)
    if not quiz:
        raise ValueError("Quiz introuvable.")

    classement = get_classement(quiz_id)
    nb_participants = len(classement)
    score_moyen = round(sum(p["score"] for p in classement) / nb_participants, 1) if nb_participants else 0.0

    nb_questions = int(quiz.get("nb_questions", 0))
    taux_par_question = [
        {"q_idx": i, "texte": quiz["questions"][i]["texte"], "taux": get_taux_bonnes_reponses(quiz_id, i)}
        for i in range(nb_questions)
    ]

    meilleure_question = max(taux_par_question, key=lambda q: q["taux"]) if taux_par_question else None
    moins_bonne_question = min(taux_par_question, key=lambda q: q["taux"]) if taux_par_question else None
    gagnant = classement[0] if classement else None

    stats = {
        "quiz_id": quiz_id,
        "titre": quiz.get("titre", ""),
        "nb_participants": nb_participants,
        "score_moyen": score_moyen,
        "gagnant_pseudo": gagnant["pseudo"] if gagnant else "",
        "gagnant_score": gagnant["score"] if gagnant else 0,
        "meilleure_question": json.dumps(meilleure_question, ensure_ascii=False) if meilleure_question else "",
        "moins_bonne_question": json.dumps(moins_bonne_question, ensure_ascii=False) if moins_bonne_question else "",
        "classement": json.dumps(classement, ensure_ascii=False),
        "date_calcul": _now_iso(),
    }

    r.hset(f"stats:{quiz_id}", mapping=stats)
    r.expire(f"stats:{quiz_id}", STATS_TTL_SECONDES)

    return stats


def get_stats(quiz_id: str) -> Optional[dict]:
    """Retourne les stats stockées d'un quiz terminé, avec classement désérialisé."""
    r = get_redis_client()
    data = r.hgetall(f"stats:{quiz_id}")
    if not data:
        return None
    data["classement"] = json.loads(data["classement"]) if data.get("classement") else []
    data["meilleure_question"] = json.loads(data["meilleure_question"]) if data.get("meilleure_question") else None
    data["moins_bonne_question"] = json.loads(data["moins_bonne_question"]) if data.get("moins_bonne_question") else None
    return data