"""Une génération par session, 60 secondes au plus."""

from __future__ import annotations

import logging
import threading
import time
import uuid

from backend.app.errors import ErreurMetier
from backend.app.limits import DUREE_JOB_S
from backend.app.pipeline.naming import slug_fichier
from backend.app.pipeline.pack import produire
from backend.app.sessions import JobEtat, Session

logger = logging.getLogger("pbi-pack")

LIBELLES = {
    "preparation": "Préparation du M et du DAX",
    "tmdl": "Modèle TMDL",
    "pbir": "Rapport PBIR",
    "compte_rendu": "Compte rendu",
    "zip": "Archive ZIP",
}
PROGRESSION = {"preparation": 15, "tmdl": 35, "pbir": 55, "compte_rendu": 75, "zip": 100}


def lancer(session: Session) -> str:
    if session.job and session.job.etat == "en_cours":
        raise ErreurMetier(
            "generation_echouee",
            "La génération s'est arrêtée. Une génération est déjà en cours pour cette session.",
        )
    if session.nettoye is None or session.journal is None:
        raise ErreurMetier(
            "generation_echouee",
            "La génération s'est arrêtée à l'étape Nettoyage. Confirmez les rôles avant de lancer.",
        )
    if session.theme is None:
        raise ErreurMetier(
            "generation_echouee",
            "La génération s'est arrêtée à l'étape Thème. Enregistrez 3 à 5 couleurs avant de lancer.",
        )
    job = JobEtat(id=str(uuid.uuid4()))
    session.job = job
    source = (session.dossier / "source.csv").read_bytes()
    contexte = {
        "nettoye": session.nettoye.copy(),
        "journal": session.journal,
        "roles": dict(session.roles or {}),
        "regles": dict(session.regles or {}),
        "date_pilote": session.date_pilote,
        "theme": session.theme,
        "profil": session.profil,
        "renommage": session.renommage,
        "encodage": session.encodage,
        "separateur": session.separateur,
        "separateur_libelle": session.profil.get("separateur_libelle", session.separateur),
        "nom_fichier": session.nom_fichier,
        "source": source,
    }
    fil = threading.Thread(target=_executer, args=(session, job, contexte), name=f"job-{job.id}", daemon=True)
    fil.start()
    return job.id


def _executer(session: Session, job: JobEtat, contexte: dict) -> None:
    etape = "preparation"

    def avancer(nom: str) -> None:
        nonlocal etape
        etape = nom
        _avancer(job, nom)
        _garde(job)

    try:
        contenu, resume = produire(contexte, avancer=avancer)
        _garde(job)
        chemin = session.dossier / "pack.zip"
        chemin.write_bytes(contenu)
        session.zip_path = chemin
        session.zip_nom = f"{slug_fichier(session.nom_fichier)}-pack-power-bi.zip"
        session.profil = {**session.profil, "generation": resume}
        job.niveau = resume["niveau"]
        job.message = resume["detail"]
        job.etat = "termine"
        job.progression = 100
        job.libelle = "Archive prête"
        logger.info("generation terminée niveau=%s", resume["niveau"])
    except ErreurMetier as exc:
        job.etat = "erreur"
        job.erreur = exc.code
        job.message = f"La génération s'est arrêtée à l'étape {LIBELLES.get(etape, etape)}. {exc.message}"
        logger.error("generation code=%s etape=%s", exc.code, etape)
    except Exception:
        job.etat = "erreur"
        job.erreur = "generation_echouee"
        job.message = f"La génération s'est arrêtée à l'étape {LIBELLES.get(etape, etape)}."
        logger.error("generation code=generation_echouee etape=%s", etape)


def _avancer(job: JobEtat, etape: str) -> None:
    job.etape = etape
    job.libelle = LIBELLES[etape]
    job.progression = PROGRESSION[etape]


def _garde(job: JobEtat) -> None:
    if time.time() - job.debut > DUREE_JOB_S:
        raise ErreurMetier(
            "generation_echouee",
            "La génération s'est arrêtée. Le délai de 60 secondes est dépassé.",
        )
