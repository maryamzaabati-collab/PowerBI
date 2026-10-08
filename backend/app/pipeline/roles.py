"""Rôles proposés. L'utilisateur les confirme avant la génération."""

from __future__ import annotations

import re

import pandas as pd

from backend.app.pipeline.naming import cle_nom
from backend.app.pipeline.nombres import parse_nombre, separateur_decimal_probable

ROLES = (
    "temporel",
    "numerique",
    "booleen",
    "geographique",
    "identifiant",
    "categorie",
    "texte",
    "ignoree",
)

LIBELLES = {
    "temporel": "Temporel",
    "numerique": "Numérique",
    "booleen": "Booléen",
    "geographique": "Géographique",
    "identifiant": "Identifiant",
    "categorie": "Catégorie",
    "texte": "Texte libre",
    "ignoree": "Ignorée",
}

NOMS_GEO = {
    "pays",
    "country",
    "ville",
    "city",
    "region",
    "departement",
    "code_postal",
    "codepostal",
    "cp",
    "commune",
    "insee",
    "lat",
    "latitude",
    "lon",
    "longitude",
}
NOMS_DATE = {"date", "jour", "mois", "periode", "annee"}
PAIRES_BOOL = (
    {"0", "1"},
    {"oui", "non"},
    {"vrai", "faux"},
    {"true", "false"},
)
CODE_TERRITORIAL = re.compile(r"^(?:\d{5}|2[ABab]\d{3})$")
DATE_NUM = re.compile(r"^\s*(?:\d{4}-\d{2}-\d{2}|\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\s*$")


def _non_vides(serie: pd.Series) -> pd.Series:
    masque = serie.map(lambda v: str(v).strip() != "")
    return serie[masque]


def _part_dates(serie: pd.Series) -> float:
    valeurs = _non_vides(serie)
    if valeurs.empty:
        return 0.0
    ok = sum(1 for v in valeurs if DATE_NUM.match(str(v)))
    return ok / len(valeurs)


def _part_nombres(serie: pd.Series, separateur: str) -> float:
    valeurs = _non_vides(serie)
    if valeurs.empty:
        return 0.0
    ok = sum(1 for v in valeurs if parse_nombre(str(v), separateur) is not None)
    return ok / len(valeurs)


def proposer_role(nom: str, serie: pd.Series, separateur: str, nb_lignes: int) -> str:
    valeurs = _non_vides(serie)
    if valeurs.empty:
        return "ignoree"
    cle = cle_nom(nom)
    if cle in NOMS_GEO or _motif_territorial(valeurs):
        return "geographique"
    part_date = _part_dates(serie)
    if part_date >= 0.9 or (cle in NOMS_DATE and part_date >= 0.5):
        return "temporel"
    distincts = {str(v).strip().lower() for v in valeurs}
    if len(distincts) == 2 and distincts in PAIRES_BOOL:
        return "booleen"
    ratio = valeurs.nunique(dropna=True) / len(valeurs)
    if ratio >= 0.98:
        return "identifiant"
    if _part_nombres(serie, separateur) >= 0.9:
        return "numerique"
    cardinalite = int(valeurs.nunique(dropna=True))
    if cardinalite <= 100 or (nb_lignes and cardinalite / nb_lignes <= 0.05):
        return "categorie"
    return "texte"


def _motif_territorial(valeurs: pd.Series) -> bool:
    if len(valeurs) < 5:
        return False
    ok = sum(1 for v in valeurs if CODE_TERRITORIAL.match(str(v).strip()))
    return ok / len(valeurs) >= 0.9


def decimal_par_defaut(separateur: str) -> str:
    return separateur_decimal_probable(separateur)
