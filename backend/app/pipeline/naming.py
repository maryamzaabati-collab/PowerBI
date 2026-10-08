"""Noms de colonnes, identifiants PBIR et citations TMDL / DAX."""

from __future__ import annotations

import re
import secrets
import unicodedata

INTERDITS = set(".,;':[]{}")
IDENTIFIANT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def sans_accents(texte: str) -> str:
    decompos = unicodedata.normalize("NFKD", texte)
    return "".join(ch for ch in decompos if not unicodedata.combining(ch))


def cle_nom(texte: str) -> str:
    brut = sans_accents(texte).lower().strip()
    brut = re.sub(r"[\s\-]+", "_", brut)
    return brut


def assainir_entete(nom: str) -> str:
    """Remplace les caractères interdits dans un identifiant TMDL."""
    morceaux: list[str] = []
    for ch in str(nom):
        if ch in INTERDITS or ch in "\r\n":
            morceaux.append("_")
        else:
            morceaux.append(ch)
    texte = "".join(morceaux).strip()
    return texte or "Colonne"


def noms_uniques(originaux: list[str]) -> list[tuple[str, str]]:
    """Retourne (nom source, nom du modèle) avec des noms de modèle uniques."""
    vus: dict[str, int] = {}
    paires: list[tuple[str, str]] = []
    for source in originaux:
        base = assainir_entete(source)
        n = vus.get(base, 0) + 1
        vus[base] = n
        modele = base if n == 1 else f"{base}_{n}"
        while modele in vus and modele != base:
            n += 1
            vus[base] = n
            modele = f"{base}_{n}"
        vus[modele] = vus.get(modele, 1)
        paires.append((str(source), modele))
    return paires


def identifiant_hex() -> str:
    """20 caractères hexadécimaux, comme les objets créés par Desktop."""
    return secrets.token_hex(10)


def nom_tmdl(nom: str) -> str:
    if IDENTIFIANT.fullmatch(nom):
        return nom
    return "'" + nom.replace("'", "''") + "'"


def ref_colonne_tmdl(table: str, colonne: str) -> str:
    return f"{nom_tmdl(table)}.{nom_tmdl(colonne)}"


def ref_dax(table: str, colonne: str) -> str:
    table_q = table.replace("'", "''")
    col_q = colonne.replace("]", "]]")
    return f"'{table_q}'[{col_q}]"


def littéral_m(texte: str) -> str:
    return '"' + texte.replace('"', '""') + '"'


def chemin_m(chemin: str) -> str:
    """Chaîne M avec les antislashs doublés."""
    return littéral_m(chemin.replace("\\", "\\\\")) if "\\" in chemin and "\\\\" not in chemin else littéral_m(chemin)


def slug_fichier(nom: str) -> str:
    base = nom.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if base.lower().endswith(".csv"):
        base = base[:-4]
    base = re.sub(r"[^A-Za-z0-9._\-àâäéèêëïîôùûüçÀÂÄÉÈÊËÏÎÔÙÛÜÇ ]+", "-", base).strip()
    return base or "donnees"
