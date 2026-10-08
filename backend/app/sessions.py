"""Sessions en mémoire, fichiers dans un dossier temporaire."""

from __future__ import annotations

import logging
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import gettempdir

import pandas as pd

from backend.app.errors import ErreurMetier
from backend.app.limits import BALAYAGE_S, DUREE_SESSION_S, GRACE_TELECHARGEMENT_S

logger = logging.getLogger("pbi-pack")


def racine_temporaire() -> Path:
    import os

    base = os.environ.get("PBI_PACK_TMP") or gettempdir()
    return Path(base) / "pbi-pack"


@dataclass
class JobEtat:
    id: str
    etat: str = "en_cours"
    etape: str = "preparation"
    libelle: str = "Préparation du M et du DAX"
    progression: int = 5
    niveau: str | None = None
    message: str | None = None
    erreur: str | None = None
    debut: float = field(default_factory=time.time)


@dataclass
class Session:
    id: str
    dossier: Path
    nom_fichier: str
    encodage: str
    separateur: str
    frame: pd.DataFrame
    profil: dict
    renommage: list[dict]
    touche: float = field(default_factory=time.time)
    regles: dict | None = None
    roles: dict | None = None
    date_pilote: str | None = None
    journal: dict | None = None
    nettoye: pd.DataFrame | None = None
    theme: dict | None = None
    contrastes: dict | None = None
    job: JobEtat | None = None
    zip_path: Path | None = None
    zip_nom: str | None = None
    fin_apres_telechargement: float | None = None


class Annuaire:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._verrou = threading.Lock()
        self._balayage: threading.Thread | None = None

    def reinitialiser(self) -> None:
        racine = racine_temporaire()
        if racine.exists():
            shutil.rmtree(racine, ignore_errors=True)
        racine.mkdir(parents=True, exist_ok=True)
        with self._verrou:
            self._sessions.clear()
        logger.info("dossier temporaire vidé")

    def demarrer_balayage(self) -> None:
        if self._balayage and self._balayage.is_alive():
            return

        def boucle() -> None:
            while True:
                time.sleep(BALAYAGE_S)
                self.balayer()

        self._balayage = threading.Thread(target=boucle, name="balayage-sessions", daemon=True)
        self._balayage.start()

    def creer(self, **kwargs) -> Session:
        identifiant = str(uuid.uuid4())
        dossier = racine_temporaire() / identifiant
        dossier.mkdir(parents=True, exist_ok=False)
        session = Session(id=identifiant, dossier=dossier, **kwargs)
        with self._verrou:
            self._sessions[identifiant] = session
        logger.info("session créée lignes=%s", len(session.frame))
        return session

    def obtenir(self, identifiant: str) -> Session:
        try:
            uuid.UUID(identifiant)
        except ValueError:
            raise ErreurMetier("session_expiree") from None
        with self._verrou:
            session = self._sessions.get(identifiant)
        if session is None:
            raise ErreurMetier("session_expiree")
        maintenant = time.time()
        if session.fin_apres_telechargement and maintenant > session.fin_apres_telechargement:
            self.supprimer(identifiant)
            raise ErreurMetier("session_expiree")
        if maintenant - session.touche > DUREE_SESSION_S:
            self.supprimer(identifiant)
            raise ErreurMetier("session_expiree")
        session.touche = maintenant
        return session

    def supprimer(self, identifiant: str) -> None:
        with self._verrou:
            session = self._sessions.pop(identifiant, None)
        if session is None:
            return
        shutil.rmtree(session.dossier, ignore_errors=True)
        logger.info("session supprimée")

    def marquer_telechargement(self, session: Session) -> None:
        session.fin_apres_telechargement = time.time() + GRACE_TELECHARGEMENT_S
        session.touche = time.time()

    def balayer(self) -> None:
        maintenant = time.time()
        with self._verrou:
            identifiants = list(self._sessions)
        for identifiant in identifiants:
            with self._verrou:
                session = self._sessions.get(identifiant)
            if session is None:
                continue
            expire = maintenant - session.touche > DUREE_SESSION_S
            grace = (
                session.fin_apres_telechargement is not None
                and maintenant > session.fin_apres_telechargement
            )
            if expire or grace:
                self.supprimer(identifiant)
                logger.info("session expirée")


annuaire = Annuaire()
