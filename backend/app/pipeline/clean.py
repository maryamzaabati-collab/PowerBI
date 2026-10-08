"""Nettoyage pandas. Les chiffres du compte rendu viennent d'ici, pas du moteur M."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from backend.app.errors import ErreurMetier
from backend.app.limits import APERCU_CELLULE, APERCU_LIGNES
from backend.app.pipeline.dates import analyser_date
from backend.app.pipeline.nombres import analyser_nombre
from backend.app.pipeline.roles import ROLES

REGLES_DEFAUT = {
    "doublons": True,
    "trim": True,
    "vides": True,
    "casse": False,
    "nombres": True,
    "dates": True,
}

ORDRE = ("trim", "vides", "doublons", "casse", "nombres", "dates")
LIBELLES_REGLES = {
    "trim": "Trim, espaces insécables et caractères de largeur nulle",
    "vides": "Chaîne vide devenue manquante",
    "doublons": "Doublons de ligne exacts, première occurrence conservée",
    "casse": "Casse des catégories alignée sur la graphie la plus fréquente",
    "nombres": "Nombres : entier si aucune partie décimale, sinon décimal",
    "dates": "Dates interprétées en jour/mois/année, écrites en AAAA-MM-JJ",
}
ZERO_WIDTH = ("\u200b", "\u200c", "\u200d", "\ufeff")
BOOL_VRAI = {"1", "oui", "vrai", "true"}
BOOL_FAUX = {"0", "non", "faux", "false"}
GEO_NOMBRE = {"lat", "latitude", "lon", "longitude"}


def normaliser_regles(regles: dict | None) -> dict:
    recues = regles or {}
    inconnues = set(recues) - set(REGLES_DEFAUT)
    if inconnues:
        raise ErreurMetier("generation_echouee", "Une règle de nettoyage n'est pas reconnue.")
    return {cle: bool(recues.get(cle, defaut)) for cle, defaut in REGLES_DEFAUT.items()}


def normaliser_roles(roles: dict, colonnes: list[str]) -> dict:
    if set(roles) != set(colonnes):
        raise ErreurMetier(
            "generation_echouee",
            "La génération s'est arrêtée. Confirmez un rôle pour chaque colonne.",
        )
    for role in roles.values():
        if role not in ROLES:
            raise ErreurMetier(
                "generation_echouee",
                "La génération s'est arrêtée. Un rôle de colonne n'est pas reconnu.",
            )
    return dict(roles)


def _est_vide(valeur: object) -> bool:
    return valeur is None or str(valeur).strip() == ""


def _trim(valeur: object) -> object:
    if valeur is None:
        return None
    texte = str(valeur).replace("\u00a0", " ")
    for marque in ZERO_WIDTH:
        texte = texte.replace(marque, "")
    return texte.strip()


def _compter(avant: pd.Series, apres: pd.Series) -> int:
    # Un changement du nombre de lignes (doublons) n'est pas une cellule modifiée.
    if len(avant) != len(apres):
        return 0
    gauche = avant.reset_index(drop=True).tolist()
    droite = apres.reset_index(drop=True).tolist()
    ecarts = 0
    for ancienne, nouvelle in zip(gauche, droite):
        if ancienne == nouvelle:
            continue
        if pd.isna(ancienne) and pd.isna(nouvelle):
            continue
        ecarts += 1
    return ecarts


def _type_colonne(serie: pd.Series, role: str) -> str:
    if role == "ignoree" or serie.dropna().empty:
        return "vide" if serie.dropna().empty else "texte"
    if role == "temporel":
        return "date"
    if role == "booleen":
        return "booléen"
    if role == "numerique" or role == "geographique" and _geo_numerique(serie.name):
        valeurs = [v for v in serie.dropna()]
        if valeurs and all(isinstance(v, int) and not isinstance(v, bool) for v in valeurs):
            return "entier"
        if valeurs and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valeurs):
            return "décimal"
    return "texte"


def _geo_numerique(nom: object) -> bool:
    from backend.app.pipeline.naming import cle_nom

    return cle_nom(str(nom)) in GEO_NOMBRE


def _aligner_casse(serie: pd.Series) -> pd.Series:
    compte: dict[str, dict[str, int]] = {}
    for valeur in serie.dropna():
        texte = str(valeur)
        cle = texte.casefold()
        compte.setdefault(cle, {})
        compte[cle][texte] = compte[cle].get(texte, 0) + 1
    choix = {cle: max(variantes, key=variantes.get) for cle, variantes in compte.items()}

    def appliquer(valeur: object) -> object:
        if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
            return None
        texte = str(valeur)
        return choix.get(texte.casefold(), texte)

    return serie.map(appliquer)


def nettoyer(
    frame: pd.DataFrame,
    roles: dict,
    regles: dict,
    separateur: str,
    date_pilote: str | None,
) -> tuple[pd.DataFrame, dict]:
    roles = normaliser_roles(roles, list(frame.columns))
    regles = normaliser_regles(regles)
    temporelles = [col for col, role in roles.items() if role == "temporel"]
    if date_pilote and date_pilote not in temporelles:
        raise ErreurMetier(
            "generation_echouee",
            "La génération s'est arrêtée. La date qui pilote le calendrier doit être une colonne temporelle.",
        )
    if temporelles and not date_pilote:
        date_pilote = temporelles[0]
    if not temporelles:
        date_pilote = None

    travail = frame.copy()
    for col in travail.columns:
        travail[col] = travail[col].map(lambda v: "" if v is None else str(v))
    manquants_avant = {
        col: float(travail[col].map(lambda v: str(v).strip() == "").mean()) if len(travail) else 0.0
        for col in travail.columns
    }
    types_avant = {col: "texte" if travail[col].notna().any() else "vide" for col in travail.columns}
    modifiees = {col: 0 for col in travail.columns}
    journal_regles = []
    ambigues: dict[str, bool] = {col: False for col in travail.columns}

    def etape(cle: str, actif: bool, action) -> None:
        avant_lignes = len(travail)
        avant = {col: travail[col].copy() for col in travail.columns}
        if actif:
            action()
        for col in travail.columns:
            modifiees[col] += _compter(avant[col], travail[col])
        journal_regles.append(
            {
                "id": cle,
                "libelle": LIBELLES_REGLES[cle],
                "active": actif,
                "lignes_avant": avant_lignes,
                "lignes_apres": len(travail),
            }
        )

    def faire_trim() -> None:
        for col in travail.columns:
            travail[col] = travail[col].map(_trim)

    def faire_vides() -> None:
        for col in travail.columns:
            travail[col] = travail[col].map(lambda v: None if v is not None and str(v) == "" else v)

    def faire_doublons() -> None:
        nonlocal travail
        travail = travail.drop_duplicates(keep="first").reset_index(drop=True)

    def faire_casse() -> None:
        for col, role in roles.items():
            if role == "categorie":
                travail[col] = _aligner_casse(travail[col])

    def faire_nombres() -> None:
        from backend.app.pipeline.naming import cle_nom

        for col, role in roles.items():
            if role == "numerique" or (role == "geographique" and cle_nom(col) in GEO_NOMBRE):
                convertis = []
                for valeur in travail[col]:
                    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
                        convertis.append(None)
                        continue
                    nombre, entier = analyser_nombre(str(valeur), separateur)
                    convertis.append(nombre if nombre is not None else None)
                travail[col] = convertis

    def faire_dates() -> None:
        if not regles["dates"]:
            return
        for col, role in roles.items():
            if role != "temporel":
                continue
            convertis = []
            for valeur in travail[col]:
                if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
                    convertis.append(None)
                    continue
                trouvee, ambigu = analyser_date(str(valeur))
                if ambigu and trouvee is not None:
                    ambigues[col] = True
                convertis.append(trouvee)
            travail[col] = convertis

    def faire_booleens() -> None:
        for col, role in roles.items():
            if role != "booleen":
                continue
            convertis = []
            for valeur in travail[col]:
                if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
                    convertis.append(None)
                    continue
                cle = str(valeur).strip().lower()
                if cle in BOOL_VRAI:
                    convertis.append(True)
                elif cle in BOOL_FAUX:
                    convertis.append(False)
                else:
                    convertis.append(None)
            travail[col] = convertis

    etape("trim", regles["trim"], faire_trim)
    etape("vides", regles["vides"], faire_vides)
    etape("doublons", regles["doublons"], faire_doublons)
    etape("casse", regles["casse"], faire_casse)
    etape("nombres", regles["nombres"], faire_nombres)
    etape("dates", regles["dates"], faire_dates)
    faire_booleens()

    types_apres = {}
    manquants_apres = {}
    for col in travail.columns:
        types_apres[col] = _type_colonne(travail[col], roles[col])
        manquants_apres[col] = float(travail[col].isna().mean()) if len(travail) else 0.0

    colonnes_journal = []
    for col in travail.columns:
        colonnes_journal.append(
            {
                "nom": col,
                "role": roles[col],
                "type_avant": types_avant[col],
                "type_apres": types_apres[col],
                "cellules_modifiees": modifiees[col],
                "manquants_avant": manquants_avant[col],
                "manquants_apres": manquants_apres[col],
                "date_ambigue": bool(ambigues[col]),
            }
        )
    journal = {
        "lignes_avant": len(frame),
        "lignes_apres": len(travail),
        "regles": journal_regles,
        "colonnes": colonnes_journal,
        "dates_ambigues": [col for col, flag in ambigues.items() if flag],
        "date_pilote": date_pilote,
        "roles": roles,
        "regles_actives": regles,
    }
    return travail, journal


def apercu_nettoye(frame: pd.DataFrame) -> dict:
    extrait = frame.head(APERCU_LIGNES)
    lignes = []
    for ligne in extrait.itertuples(index=False, name=None):
        cellules = []
        for valeur in ligne:
            cellules.append(_afficher(valeur)[:APERCU_CELLULE])
        lignes.append(cellules)
    return {"colonnes": list(frame.columns), "lignes": lignes}


def _afficher(valeur: object) -> str:
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return ""
    if isinstance(valeur, datetime):
        return valeur.date().isoformat()
    if isinstance(valeur, date):
        return valeur.isoformat()
    if isinstance(valeur, bool):
        return "true" if valeur else "false"
    if isinstance(valeur, int) and not isinstance(valeur, bool):
        return str(valeur)
    if isinstance(valeur, float):
        return format(valeur, "f").rstrip("0").rstrip(".") if valeur.is_integer() else format(valeur, "f")
    return str(valeur)


def ecrire_csv(frame: pd.DataFrame, chemin) -> None:
    """UTF-8 avec BOM, virgule, point décimal. Apostrophe devant une formule."""
    import csv

    with open(chemin, "w", encoding="utf-8-sig", newline="") as fichier:
        ecrivain = csv.writer(fichier)
        ecrivain.writerow(list(frame.columns))
        for ligne in frame.itertuples(index=False, name=None):
            ecrivain.writerow([_cellule_csv(valeur) for valeur in ligne])


def _cellule_csv(valeur: object) -> str:
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return ""
    if isinstance(valeur, datetime):
        return valeur.date().isoformat()
    if isinstance(valeur, date):
        return valeur.isoformat()
    if isinstance(valeur, bool):
        return "true" if valeur else "false"
    if isinstance(valeur, int) and not isinstance(valeur, bool):
        return str(valeur)
    if isinstance(valeur, float):
        if valeur.is_integer():
            return str(int(valeur))
        return format(valeur, "f")
    texte = str(valeur)
    if texte[:1] in "=+-@":
        return "'" + texte
    return texte
