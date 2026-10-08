"""Erreurs renvoyées au navigateur, sans trace technique."""

from fastapi import HTTPException

MESSAGES = {
    "csv_vide": "Le fichier ne contient aucune ligne de données.",
    "csv_trop_volumineux": "Le fichier dépasse 50 Mo ou 200 000 lignes.",
    "csv_trop_de_colonnes": "Plus de 80 colonnes.",
    "csv_illisible": "Encodage ou séparateur inutilisable. Choisir les deux et relancer.",
    "csv_entete_absente": "La première ligne est vide.",
    "pas_un_csv": "Seul un fichier .csv est accepté.",
    "session_expiree": "Déposer le fichier à nouveau.",
    "generation_echouee": "La génération s'est arrêtée. Le message précise l'étape.",
}


class ErreurMetier(Exception):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.message = message or MESSAGES[code]
        super().__init__(self.message)


def http_erreur(exc: ErreurMetier) -> HTTPException:
    return HTTPException(status_code=400, detail={"code": exc.code, "message": exc.message})
