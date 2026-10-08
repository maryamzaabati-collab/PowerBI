"""Profil du fichier et des colonnes, avant nettoyage."""

from __future__ import annotations

import pandas as pd

from backend.app.limits import APERCU_CELLULE, APERCU_LIGNES
from backend.app.pipeline.dates import analyser_date
from backend.app.pipeline.nombres import analyser_nombre, separateur_decimal_probable
from backend.app.pipeline.roles import LIBELLES, proposer_role

def _tronquer(valeur: object) -> str:
    texte = "" if valeur is None else str(valeur)
    if len(texte) > APERCU_CELLULE:
        return texte[:APERCU_CELLULE]
    return texte


def _apercu(frame: pd.DataFrame) -> dict:
    extrait = frame.head(APERCU_LIGNES)
    return {
        "colonnes": list(frame.columns),
        "lignes": [[_tronquer(cell) for cell in ligne] for ligne in extrait.itertuples(index=False, name=None)],
    }


def _entete_ressemble_a_des_donnees(noms_source: list[str], separateur: str) -> bool:
    utiles = [nom for nom in noms_source if str(nom).strip()]
    if not utiles:
        return False
    nombres = sum(1 for nom in utiles if analyser_nombre(str(nom), separateur)[0] is not None)
    return nombres / len(utiles) > 0.5


def _aberrantes(valeurs: list[float]) -> dict | None:
    if len(valeurs) < 20:
        return None
    serie = pd.Series(valeurs)
    q1 = float(serie.quantile(0.25))
    q3 = float(serie.quantile(0.75))
    iqr = q3 - q1
    bas, haut = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    hors = [v for v in valeurs if v < bas or v > haut]
    return {
        "compte": len(hors),
        "borne_basse": bas,
        "borne_haute": haut,
        "exemples": [float(v) for v in hors[:20]],
    }


def profiler(frame: pd.DataFrame, meta: dict) -> dict:
    separateur = meta["separateur"]
    nb = len(frame)
    # Doublons exacts après trim, avant les autres règles.
    trimme = frame.map(lambda v: str(v).replace("\u00a0", " ").strip())
    doublons = int(trimme.duplicated(keep="first").sum())
    colonnes = []
    for source, modele in ((item["source"], item["modele"]) for item in meta["renommage"]):
        serie = frame[modele]
        role = proposer_role(modele, serie, separateur, nb)
        non_vides = serie.map(lambda v: str(v).strip() != "")
        nb_non_vides = int(non_vides.sum())
        distincts = int(serie[non_vides].nunique()) if nb_non_vides else 0
        manquants = 1 - (nb_non_vides / nb) if nb else 0
        part_doublons = 0.0 if nb_non_vides == 0 else 1 - (distincts / nb_non_vides)
        nombres = [analyser_nombre(str(v), separateur)[0] for v in serie[non_vides]]
        nombres_ok = [v for v in nombres if isinstance(v, (int, float))]
        dates = [analyser_date(str(v)) for v in serie[non_vides]]
        ambigu = any(ok and flag for ok, flag in dates if ok is not None)
        colonnes.append(
            {
                "nom": modele,
                "nom_source": source,
                "role_propose": role,
                "role_libelle": LIBELLES[role],
                "type_propose": {
                    "temporel": "date",
                    "numerique": "nombre",
                    "booleen": "booléen",
                    "ignoree": "vide",
                }.get(role, "texte"),
                "manquants": manquants,
                "cardinalite": distincts,
                "ratio_cardinalite": (distincts / nb) if nb else 0,
                "part_doublons": part_doublons,
                "date_ambigue": bool(ambigu) and role == "temporel",
                "aberrantes": _aberrantes(nombres_ok) if role == "numerique" else None,
            }
        )
    avertissement = None
    if _entete_ressemble_a_des_donnees([item["source"] for item in meta["renommage"]], separateur):
        avertissement = (
            "La première ligne ressemble à des données. Elle est quand même utilisée comme en-tête."
        )
    return {
        "nom_fichier": meta.get("nom_fichier"),
        "lignes": nb,
        "colonnes_nombre": len(frame.columns),
        "doublons_exacts": doublons,
        "encodage": meta["encodage"],
        "separateur": separateur,
        "separateur_libelle": meta["separateur_libelle"],
        "decimal": separateur_decimal_probable(separateur),
        "avertissement_entete": avertissement,
        "renommage": meta["renommage"],
        "colonnes": colonnes,
        "apercu": _apercu(frame),
    }
