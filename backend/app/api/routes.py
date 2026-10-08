"""Routes de session. Les chemins n'acceptent qu'un UUID."""

from __future__ import annotations

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from backend.app.errors import ErreurMetier
from backend.app.limits import TAILLE_MAX_OCTETS
from backend.app.pipeline.clean import apercu_nettoye, nettoyer, normaliser_regles
from backend.app.pipeline.job import lancer
from backend.app.pipeline.lecture import lire_csv, verifier_nom, verifier_taille
from backend.app.pipeline.profile import profiler
from backend.app.pipeline.theme import construire_theme
from backend.app.sessions import annuaire

routeur = APIRouter(prefix="/api")


class ParseIn(BaseModel):
    encodage: str | None = None
    separateur: str | None = None


class CleanIn(BaseModel):
    regles: dict = Field(default_factory=dict)
    roles: dict
    date_pilote: str | None = None


class ThemeIn(BaseModel):
    couleurs: list[str]


@routeur.post("/sessions")
async def creer_session(fichier: UploadFile = File(...)):
    verifier_nom(fichier.filename)
    contenu = await _lire_limite(fichier)
    frame, meta = lire_csv(contenu)
    meta["nom_fichier"] = fichier.filename
    profil = profiler(frame, meta)
    profil["nom_fichier"] = fichier.filename
    session = annuaire.creer(
        nom_fichier=fichier.filename or "donnees.csv",
        encodage=meta["encodage"],
        separateur=meta["separateur"],
        frame=frame,
        profil=profil,
        renommage=meta["renommage"],
    )
    (session.dossier / "source.csv").write_bytes(contenu)
    return {"session": session.id, "profil": profil}


@routeur.patch("/sessions/{session_id}/parse")
async def relire(session_id: str, corps: ParseIn):
    session = annuaire.obtenir(session_id)
    contenu = (session.dossier / "source.csv").read_bytes()
    frame, meta = lire_csv(contenu, encodage=corps.encodage, separateur=corps.separateur)
    meta["nom_fichier"] = session.nom_fichier
    profil = profiler(frame, meta)
    profil["nom_fichier"] = session.nom_fichier
    session.frame = frame
    session.encodage = meta["encodage"]
    session.separateur = meta["separateur"]
    session.renommage = meta["renommage"]
    session.profil = profil
    session.nettoye = None
    session.journal = None
    session.zip_path = None
    return {"session": session.id, "profil": profil}


@routeur.post("/sessions/{session_id}/clean")
async def nettoyer_session(session_id: str, corps: CleanIn):
    session = annuaire.obtenir(session_id)
    regles = normaliser_regles(corps.regles)
    nettoye, journal = nettoyer(session.frame, corps.roles, regles, session.separateur, corps.date_pilote)
    journal["encodage"] = session.encodage
    journal["separateur"] = session.separateur
    session.regles = regles
    session.roles = corps.roles
    session.date_pilote = journal["date_pilote"]
    session.journal = journal
    session.nettoye = nettoye
    session.zip_path = None
    session.job = None
    return {"journal": journal, "apercu": apercu_nettoye(nettoye)}


@routeur.put("/sessions/{session_id}/theme")
async def enregistrer_theme(session_id: str, corps: ThemeIn):
    session = annuaire.obtenir(session_id)
    resultat = construire_theme(corps.couleurs)
    session.theme = resultat["theme"]
    session.contrastes = resultat
    session.zip_path = None
    return resultat


@routeur.post("/sessions/{session_id}/generate")
async def generer(session_id: str):
    session = annuaire.obtenir(session_id)
    job = lancer(session)
    return {"job": job}


@routeur.get("/sessions/{session_id}/jobs/{job_id}")
async def etat_job(session_id: str, job_id: str):
    session = annuaire.obtenir(session_id)
    job = session.job
    if job is None or job.id != job_id:
        raise ErreurMetier("session_expiree")
    return {
        "job": job.id,
        "etat": job.etat,
        "etape": job.etape,
        "libelle": job.libelle,
        "progression": job.progression,
        "niveau": job.niveau,
        "message": job.message,
        "erreur": job.erreur,
    }


@routeur.get("/sessions/{session_id}/download")
async def telecharger(session_id: str):
    session = annuaire.obtenir(session_id)
    if session.job is None or session.job.etat != "termine" or session.zip_path is None:
        raise ErreurMetier(
            "generation_echouee",
            "La génération s'est arrêtée. Le téléchargement attend que le job soit terminé.",
        )
    annuaire.marquer_telechargement(session)
    return FileResponse(
        session.zip_path,
        media_type="application/zip",
        filename=session.zip_nom or "pack-power-bi.zip",
    )


@routeur.delete("/sessions/{session_id}")
async def oublier(session_id: str):
    annuaire.obtenir(session_id)
    annuaire.supprimer(session_id)
    return Response(status_code=204)


async def _lire_limite(fichier: UploadFile) -> bytes:
    morceaux: list[bytes] = []
    total = 0
    while True:
        bloc = await fichier.read(1024 * 1024)
        if not bloc:
            break
        total += len(bloc)
        if total > TAILLE_MAX_OCTETS:
            raise ErreurMetier("csv_trop_volumineux")
        morceaux.append(bloc)
    contenu = b"".join(morceaux)
    verifier_taille(len(contenu))
    return contenu
