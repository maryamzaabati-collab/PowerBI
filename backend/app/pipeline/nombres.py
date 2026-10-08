"""Lecture des nombres. Le séparateur de champ fixe le candidat décimal."""

from __future__ import annotations

import re

_NOMBRE = re.compile(r"\d+(?:\.\d+)?")


def separateur_decimal_probable(separateur_champ: str) -> str:
    return "," if separateur_champ == ";" else "."


def parse_nombre(texte: str, separateur_champ: str) -> float | None:
    valeur, _ = analyser_nombre(texte, separateur_champ)
    return valeur


def analyser_nombre(texte: str, separateur_champ: str) -> tuple[int | float | None, bool]:
    """Retourne (valeur, est_entier). None si la cellule n'est pas un nombre."""
    brut = str(texte).strip().replace("\u00a0", "").replace(" ", "")
    if not brut:
        return None, False
    negatif = brut.startswith("-")
    if brut[0] in "+-":
        brut = brut[1:]
    if not brut:
        return None, False
    decimal = separateur_decimal_probable(separateur_champ)
    millier = "." if decimal == "," else ","
    if decimal in brut and millier in brut and brut.rfind(decimal) < brut.rfind(millier):
        decimal, millier = millier, decimal
    sans_millier = brut.replace(millier, "")
    if sans_millier.count(decimal) > 1:
        return None, False
    partie = sans_millier.split(decimal)
    normalise = partie[0] + ("." + partie[1] if len(partie) == 2 else "")
    if not _NOMBRE.fullmatch(normalise):
        return None, False
    est_entier = len(partie) == 1 or set(partie[1]) <= {"0"}
    if est_entier:
        return (-1 if negatif else 1) * int(partie[0] or "0"), True
    valeur = float(normalise)
    return (-valeur if negatif else valeur), False
