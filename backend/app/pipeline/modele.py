"""Grain du modèle : Donnees, Calendrier, dimension seulement si le préfixe se répète."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backend.app.pipeline.naming import cle_nom, nom_tmdl


@dataclass
class Dimension:
    nom: str
    prefixe: str
    cle: str
    colonnes: list[str]


@dataclass
class Plan:
    roles: dict
    mesures: list[str]
    mesures_non_generees: list[str]
    date_pilote: str | None
    dimensions: list[Dimension] = field(default_factory=list)
    colonnes_faits: list[str] = field(default_factory=list)
    categorie_principale: tuple[str, str] | None = None
    categorie_secondaire: tuple[str, str] | None = None
    cardinalites: dict[str, int] = field(default_factory=dict)
    paire_correlation: tuple[str, str, float] | None = None


def _cle_groupe(colonnes: list[str], roles: dict, prefixe: str) -> str | None:
    for colonne in colonnes:
        if colonne == f"{prefixe}_id" or colonne.endswith("_id") or roles.get(colonne) == "identifiant":
            return colonne
    return None


def extraire_dimensions(frame: pd.DataFrame, roles: dict, date_pilote: str | None) -> list[Dimension]:
    groupes: dict[str, list[str]] = {}
    for colonne in frame.columns:
        if "_" not in colonne:
            continue
        prefixe = colonne.split("_", 1)[0]
        if prefixe:
            groupes.setdefault(prefixe, []).append(colonne)
    dimensions: list[Dimension] = []
    for prefixe, colonnes in groupes.items():
        if len(colonnes) < 2:
            continue
        cle = _cle_groupe(colonnes, roles, prefixe)
        if cle is None or cle == date_pilote:
            continue
        serie = frame[cle].dropna()
        if serie.empty or serie.nunique(dropna=True) >= len(serie):
            continue
        retenues = [col for col in colonnes if col != date_pilote]
        if len(retenues) < 2 or cle not in retenues:
            continue
        nom = "Dim_" + "".join(morceau[:1].upper() + morceau[1:] for morceau in prefixe.split("_") if morceau)
        dimensions.append(Dimension(nom=nom, prefixe=prefixe, cle=cle, colonnes=retenues))
        if len(dimensions) == 6:
            break
    return dimensions


def _table_de(plan_dims: list[Dimension], colonne: str) -> str:
    for dimension in plan_dims:
        if colonne in dimension.colonnes and colonne != dimension.cle:
            return dimension.nom
        if colonne == dimension.cle:
            return dimension.nom
    return "Donnees"


def cardinalite(serie: pd.Series) -> int:
    return int(serie.dropna().nunique())


def construire_plan(frame: pd.DataFrame, roles: dict, date_pilote: str | None) -> Plan:
    dimensions = extraire_dimensions(frame, roles, date_pilote)
    deplacees = {col for dim in dimensions for col in dim.colonnes if col != dim.cle}
    colonnes_faits = [col for col in frame.columns if col not in deplacees]
    mesures = [col for col in colonnes_faits if roles.get(col) == "numerique"]
    gardees, reste = mesures[:8], mesures[8:]
    categories = []
    for col, role in roles.items():
        if role == "categorie":
            categories.append((col, cardinalite(frame[col]), _table_de(dimensions, col)))
    categories.sort(key=lambda item: (item[1], item[0]))
    principale = (categories[0][2], categories[0][0]) if categories else None
    secondaire = (categories[1][2], categories[1][0]) if len(categories) > 1 else None
    cards = {col: cardinalite(frame[col]) for col in frame.columns}
    return Plan(
        roles=roles,
        mesures=gardees,
        mesures_non_generees=reste,
        date_pilote=date_pilote if date_pilote and frame[date_pilote].notna().any() else None,
        dimensions=dimensions,
        colonnes_faits=colonnes_faits,
        categorie_principale=principale,
        categorie_secondaire=secondaire,
        cardinalites=cards,
        paire_correlation=_correlation(frame, gardees),
    )


def _correlation(frame: pd.DataFrame, mesures: list[str]) -> tuple[str, str, float] | None:
    if len(mesures) < 2:
        return None
    nombres = frame[mesures].apply(pd.to_numeric, errors="coerce")
    meilleur: tuple[str, str, float] | None = None
    for i, gauche in enumerate(mesures):
        for droite in mesures[i + 1 :]:
            paire = nombres[[gauche, droite]].dropna()
            if len(paire) < 3 or paire[gauche].std() == 0 or paire[droite].std() == 0:
                continue
            valeur = float(paire[gauche].corr(paire[droite]))
            if meilleur is None or abs(valeur) > abs(meilleur[2]):
                meilleur = (gauche, droite, valeur)
    return meilleur


def nom_table(nom: str) -> str:
    return nom_tmdl(nom)


def cle_colonne(nom: str) -> str:
    return cle_nom(nom)
