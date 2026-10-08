"""Dates en jour/mois/année. Une valeur ambiguë est signalée, pas réinterprétée."""

from __future__ import annotations

import re
from datetime import date

_ISO = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})")
_DMY = re.compile(r"^\s*(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})\s*$")


def _annee(valeur: int) -> int:
    if valeur >= 100:
        return valeur
    return 1900 + valeur if valeur >= 70 else 2000 + valeur


def analyser_date(texte: str) -> tuple[date | None, bool]:
    brut = str(texte).strip()
    if not brut:
        return None, False
    iso = _ISO.match(brut)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3))), False
        except ValueError:
            return None, False
    dmy = _DMY.match(brut)
    if not dmy:
        return None, False
    jour, mois, annee = int(dmy.group(1)), int(dmy.group(2)), _annee(int(dmy.group(3)))
    ambigu = jour <= 12 and mois <= 12
    try:
        return date(annee, mois, jour), ambigu
    except ValueError:
        return None, False
