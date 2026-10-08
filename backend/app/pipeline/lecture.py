"""Lecture du CSV : encodage, séparateur, limites. Aucun appel réseau."""

from __future__ import annotations

import csv
import io

import pandas as pd
from charset_normalizer import from_bytes

from backend.app.errors import ErreurMetier
from backend.app.limits import COLONNES_MAX, LIGNES_MAX, TAILLE_MAX_OCTETS
from backend.app.pipeline.naming import noms_uniques

CANDIDATS_SEP = [",", ";", "\t", "|"]
SEPAREURS_ACCEPTES = {",": ",", ";": ";", "tab": "\t", "\t": "\t", "|": "|"}


def verifier_taille(nombre_octets: int) -> None:
    if nombre_octets > TAILLE_MAX_OCTETS:
        raise ErreurMetier("csv_trop_volumineux")


def verifier_nom(nom: str | None) -> None:
    if not nom or not nom.lower().endswith(".csv"):
        raise ErreurMetier("pas_un_csv")


def normaliser_separateur(valeur: str) -> str:
    if valeur not in SEPAREURS_ACCEPTES:
        raise ErreurMetier("csv_illisible")
    return SEPAREURS_ACCEPTES[valeur]


def separateur_libelle(sep: str) -> str:
    return {"\t": "tabulation", ",": "virgule", ";": "point-virgule", "|": "barre verticale"}.get(sep, sep)


def _decoder(data: bytes, encodage: str) -> str:
    try:
        return data.decode(encodage)
    except UnicodeDecodeError as exc:
        raise ErreurMetier("csv_illisible") from exc


def detecter_encodage(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    resultat = from_bytes(data[:262_144]).best()
    if resultat is not None:
        nom = (resultat.encoding or "").lower().replace("_", "-")
        if nom in {"utf-8", "utf-8-sig"}:
            return "utf-8-sig" if data.startswith(b"\xef\xbb\xbf") else "utf-8"
        if nom in {"cp1252", "windows-1252"}:
            return "cp1252"
        if nom in {"iso-8859-1", "latin-1", "latin1"}:
            return "latin-1"
    for encodage in ("utf-8", "cp1252", "latin-1"):
        try:
            data.decode(encodage)
            return encodage
        except UnicodeDecodeError:
            continue
    raise ErreurMetier("csv_illisible")


def detecter_separateur(texte: str) -> str:
    echantillon = "\n".join(texte.splitlines()[:40])
    if not echantillon.strip():
        raise ErreurMetier("csv_illisible")
    meilleur: str | None = None
    meilleur_score = (-1.0, -1)
    for sep in CANDIDATS_SEP:
        try:
            lignes = list(csv.reader(io.StringIO(echantillon), delimiter=sep))
        except csv.Error:
            continue
        largeurs = [len(ligne) for ligne in lignes if any(cell.strip() for cell in ligne)]
        if not largeurs:
            continue
        mode = max(set(largeurs), key=largeurs.count)
        coherence = sum(1 for largeur in largeurs if largeur == mode) / len(largeurs)
        score = (coherence, mode if coherence >= 0.8 else 0)
        if score > meilleur_score:
            meilleur_score = score
            meilleur = sep
    if meilleur is None or meilleur_score[0] < 0.6:
        raise ErreurMetier("csv_illisible")
    return meilleur


def lire_csv(data: bytes, encodage: str | None = None, separateur: str | None = None) -> tuple[pd.DataFrame, dict]:
    verifier_taille(len(data))
    if not data.strip():
        raise ErreurMetier("csv_vide")
    enc = encodage or detecter_encodage(data)
    if enc not in {"utf-8", "utf-8-sig", "cp1252", "latin-1"}:
        raise ErreurMetier("csv_illisible")
    texte = _decoder(data, enc)
    if texte.startswith("\ufeff"):
        texte = texte.lstrip("\ufeff")
    sep = normaliser_separateur(separateur) if separateur else detecter_separateur(texte)
    try:
        lecteur = csv.reader(io.StringIO(texte), delimiter=sep)
        entete = next(lecteur, None)
    except csv.Error as exc:
        raise ErreurMetier("csv_illisible") from exc
    if entete is None or not any(cell.strip() for cell in entete):
        raise ErreurMetier("csv_entete_absente")
    if len(entete) > COLONNES_MAX:
        raise ErreurMetier("csv_trop_de_colonnes")
    lignes: list[list[str]] = []
    largeur = len(entete)
    try:
        for ligne in lecteur:
            if len(lignes) >= LIGNES_MAX:
                raise ErreurMetier("csv_trop_volumineux")
            if len(ligne) == 1 and ligne[0] == "" and largeur > 1:
                continue
            if len(ligne) != largeur:
                raise ErreurMetier("csv_illisible")
            lignes.append(ligne)
    except csv.Error as exc:
        raise ErreurMetier("csv_illisible") from exc
    if not lignes:
        raise ErreurMetier("csv_vide")
    paires = noms_uniques(entete)
    colonnes = [modele for _, modele in paires]
    frame = pd.DataFrame(lignes, columns=colonnes)
    meta = {
        "encodage": enc,
        "separateur": sep,
        "separateur_libelle": separateur_libelle(sep),
        "renommage": [{"source": source, "modele": modele} for source, modele in paires],
    }
    return frame, meta
