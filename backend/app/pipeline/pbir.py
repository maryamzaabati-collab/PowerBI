"""Rapport PBIR. Niveau A si les visual.json passent le schéma, sinon B puis C."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.pipeline.modele import Plan
from backend.app.pipeline.naming import identifiant_hex
from backend.app.pipeline.schema_check import erreurs

MANIFEST = json.loads(
    (Path(__file__).resolve().parents[2] / "templates" / "pbip" / "manifest.json").read_text(encoding="utf-8")
)
SCHEMAS = MANIFEST["schemas"]
VERSIONS = MANIFEST["reportVersionAtImport"]


def _literal(texte: str) -> dict:
    return {"expr": {"Literal": {"Value": "'" + texte.replace("'", "''") + "'"}}}


def _colonne(table: str, nom: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": nom}}


def _mesure(nom: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "Donnees"}}, "Property": nom}}


def _projection(field: dict, ref: str) -> dict:
    return {"field": field, "queryRef": ref, "nativeQueryRef": ref}


def _requete(roles: dict, tri: list | None = None) -> dict:
    etat = {role: {"projections": projections} for role, projections in roles.items()}
    requete: dict = {"queryState": etat}
    if tri:
        requete["sortDefinition"] = {"sort": tri, "isDefaultSort": False}
    return requete


def _visuel(type_visuel: str, x: float, y: float, w: float, h: float, titre: str, requete: dict | None, filtre=None) -> dict:
    corps = {
        "$schema": SCHEMAS["visual"],
        "name": identifiant_hex(),
        "position": {"x": x, "y": y, "z": 0, "height": h, "width": w, "tabOrder": 0},
        "visual": {
            "visualType": type_visuel,
            "visualContainerObjects": {"title": [{"properties": {"text": _literal(titre)}}]},
        },
    }
    if requete:
        corps["visual"]["query"] = requete
    if filtre:
        corps["filterConfig"] = filtre
    return corps


def _texte(x: float, y: float, w: float, h: float, texte: str, taille: str = "14px", gras: bool = False) -> dict:
    style = {"fontFamily": "Segoe UI Semibold" if gras else "Segoe UI", "fontSize": taille}
    if gras:
        style["fontWeight"] = "bold"
    return {
        "$schema": SCHEMAS["visual"],
        "name": identifiant_hex(),
        "position": {"x": x, "y": y, "z": 0, "height": h, "width": w, "tabOrder": 0},
        "visual": {
            "visualType": "textbox",
            "objects": {
                "general": [
                    {
                        "properties": {
                            "paragraphs": [
                                {
                                    "textRuns": [
                                        {
                                            "value": texte,
                                            "textStyle": style,
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ]
            },
        },
    }


def _filtre_top(table: str, colonne: str) -> dict:
    return {
        "filters": [
            {
                "name": identifiant_hex(),
                "field": _colonne(table, colonne),
                "type": "TopN",
                "filter": {
                    "Version": 2,
                    "From": [{"Name": "t", "Entity": table, "Type": 0}],
                    "Where": [{"Condition": {"VisualTopN": {"ItemCount": 10}}}],
                },
                "howCreated": "User",
            }
        ]
    }


def _valide(instance: dict, schema: str) -> bool:
    return not erreurs(instance, schema)


def _poser(visuel: dict, fragile: bool, secours: str) -> tuple[dict | None, str | None]:
    """Retourne le visuel gardé et un motif si on a dégradé."""
    if _valide(visuel, SCHEMAS["visual"]):
        return visuel, None
    if fragile:
        return None, "omis"
    zone = _texte(
        visuel["position"]["x"],
        visuel["position"]["y"],
        visuel["position"]["width"],
        visuel["position"]["height"],
        secours,
    )
    if _valide(zone, SCHEMAS["visual"]):
        return zone, "texte"
    return None, "retire"


def generer_pbir(plan: Plan, theme: dict) -> dict:
    pages = _pages(plan)
    partiel = False
    repli_texte = False
    for page in pages:
        gardes = []
        for item in page["visuels"]:
            visuel = item["json"]
            if item.get("topn") and "filterConfig" in visuel and not _valide(visuel, SCHEMAS["visual"]):
                visuel = {cle: valeur for cle, valeur in visuel.items() if cle != "filterConfig"}
                partiel = True
                item["note"] = "Filtre top 10 retiré : il ne passe pas le schéma."
            pose, motif = _poser(visuel, item["fragile"], item["secours"])
            if motif == "omis":
                partiel = True
                item["note"] = "Segment omis : le visual.json ne passe pas le schéma."
            elif motif == "texte":
                repli_texte = True
                item["note"] = "Zone de texte à la place du visuel."
            elif motif == "retire":
                repli_texte = True
                item["note"] = "Visuel retiré : ni le visuel ni la zone de texte ne passent le schéma."
            if pose is not None:
                gardes.append(pose)
            item["pose"] = pose
        page["gardes"] = gardes

    fichiers = _coquille(theme, pages, avec_visuels=True)
    coquille_ok = _coquille_valide(fichiers)
    visuels_ok = all(_valide(visuel, SCHEMAS["visual"]) for page in pages for visuel in page["gardes"])
    if not coquille_ok or not visuels_ok:
        for page in pages:
            page["gardes"] = []
        fichiers = _coquille(theme, pages, avec_visuels=False)
        niveau = "C"
        detail = "Le rapport avec visuels ne passe pas les schémas vendored. Pages conservées, sans visuel."
    elif repli_texte:
        niveau = "B"
        detail = "Au moins un visuel a été remplacé par une zone de texte qui liste les champs à poser."
    elif partiel:
        niveau = "A partiel"
        detail = "Visuels natifs posés. Un segment ou le filtre top 10 a été omis."
    else:
        niveau = "A"
        detail = "Les visual.json passent les schémas vendored. Ce n'est pas une ouverture garantie dans Desktop."
    return {"fichiers": fichiers, "niveau": niveau, "detail": detail, "pages": _resume(pages)}


# Grille de page 1280 × 720 : marge 24, gouttière 16, titre en haut, contenu en dessous.
LARGEUR, HAUTEUR = 1280, 720
MARGE, GOUTTIERE = 24, 16
HAUT_CONTENU = 72
LARGEUR_UTILE = LARGEUR - 2 * MARGE
HAUTEUR_UTILE = HAUTEUR - MARGE - HAUT_CONTENU
COLONNE_DROITE = 320


def _colonnes(nombre: int, largeur: float = LARGEUR_UTILE, x: float = MARGE) -> list[tuple[float, float]]:
    """Découpe une largeur en colonnes égales : [(x, largeur), …]."""
    taille = (largeur - (nombre - 1) * GOUTTIERE) / nombre
    return [(x + index * (taille + GOUTTIERE), taille) for index in range(nombre)]


def _titre_page(nom: str) -> dict:
    return {
        "fragile": False,
        "secours": nom,
        "titre": True,
        "json": _texte(MARGE, 16, LARGEUR_UTILE, 44, nom, taille="20px", gras=True),
    }


def _message(texte: str, secours: str) -> dict:
    return {"fragile": False, "secours": secours, "json": _texte(MARGE, HAUT_CONTENU, LARGEUR_UTILE, 200, texte)}


def _barres(table: str, colonne: str, mesure: str, x: float, y: float, w: float, h: float, *, top: bool, secours: str) -> dict:
    tri = [{"field": _mesure(mesure), "direction": "Descending"}]
    return {
        "fragile": False,
        "topn": top,
        "secours": secours,
        "json": _visuel(
            "clusteredBarChart",
            x,
            y,
            w,
            h,
            colonne,
            _requete(
                {
                    "Category": [_projection(_colonne(table, colonne), f"{table}.{colonne}")],
                    "Y": [_projection(_mesure(mesure), f"Donnees.{mesure}")],
                },
                tri=tri,
            ),
            filtre=_filtre_top(table, colonne) if top else None,
        ),
    }


def _courbe(plan: Plan, x: float, y: float, w: float, h: float) -> dict:
    projections = [_projection(_mesure(f"Total {col}"), f"Donnees.Total {col}") for col in plan.mesures[:3]]
    return {
        "fragile": False,
        "secours": "Courbe à poser : Calendrier[Date] et les mesures Total.",
        "json": _visuel(
            "lineChart",
            x,
            y,
            w,
            h,
            "Évolution",
            _requete(
                {
                    "Category": [_projection(_colonne("Calendrier", "Date"), "Calendrier.Date")],
                    "Y": projections,
                },
                tri=[{"field": _colonne("Calendrier", "Date"), "direction": "Ascending"}],
            ),
        ),
    }


def _carte(mesure: str, libelle: str, x: float, y: float, w: float, h: float) -> dict:
    return {
        "fragile": False,
        "secours": f"Carte à poser : {libelle}.",
        "json": _visuel("card", x, y, w, h, mesure, _requete({"Values": [_projection(_mesure(mesure), f"Donnees.{mesure}")]})),
    }


def _segment(table: str, colonne: str, titre: str, x: float, y: float, w: float, h: float, secours: str) -> dict:
    return {
        "fragile": True,
        "secours": secours,
        "json": _visuel(
            "slicer", x, y, w, h, titre, _requete({"Values": [_projection(_colonne(table, colonne), f"{table}.{colonne}")]})
        ),
    }


def _anneau(
    table: str, colonne: str, x: float, y: float, w: float, h: float, secours: str, mesure: str = "Part du total"
) -> dict:
    return {
        "fragile": False,
        "secours": secours,
        "json": _visuel(
            "donutChart",
            x,
            y,
            w,
            h,
            "Part du total",
            _requete(
                {
                    "Category": [_projection(_colonne(table, colonne), f"{table}.{colonne}")],
                    "Y": [_projection(_mesure(mesure), f"Donnees.{mesure}")],
                }
            ),
        ),
    }


def _pages(plan: Plan) -> list[dict]:
    cartes = [("Nombre de lignes", "Nombre de lignes de Donnees")]
    for colonne in plan.mesures[:3]:
        cartes.append((f"Total {colonne}", f"Mesure Total {colonne}"))
    cartes = cartes[:4]

    # Vue d'ensemble : bandeau de KPI, puis tendance et classement côte à côte.
    page_vue = {"nom": "Vue d'ensemble", "visuels": [_titre_page("Vue d'ensemble")]}
    hauteur_kpi = 104
    for (mesure, libelle), (x, w) in zip(cartes, _colonnes(len(cartes))):
        page_vue["visuels"].append(_carte(mesure, libelle, x, HAUT_CONTENU, w, hauteur_kpi))
    y2 = HAUT_CONTENU + hauteur_kpi + GOUTTIERE
    h2 = HAUTEUR - MARGE - y2
    if plan.categorie_principale and plan.mesures:
        table, colonne = plan.categorie_principale
        mesure = f"Total {plan.mesures[0]}"
        secours = f"Barres groupées à poser : {table}[{colonne}] et {mesure}."
        segment = plan.cardinalites.get(colonne, 99) <= 12
        if plan.date_pilote:
            (xa, wa), (xb, wb) = _colonnes(2)
            page_vue["visuels"].append(_courbe(plan, xa, y2, wa, h2))
            page_vue["visuels"].append(_barres(table, colonne, mesure, xb, y2, wb, h2, top=True, secours=secours))
        elif segment:
            largeur = LARGEUR_UTILE - COLONNE_DROITE - GOUTTIERE
            page_vue["visuels"].append(_barres(table, colonne, mesure, MARGE, y2, largeur, h2, top=True, secours=secours))
            page_vue["visuels"].append(
                _segment(table, colonne, colonne, MARGE + largeur + GOUTTIERE, y2, COLONNE_DROITE, h2, f"Segment à poser sur {table}[{colonne}].")
            )
        else:
            page_vue["visuels"].append(_barres(table, colonne, mesure, MARGE, y2, LARGEUR_UTILE, h2, top=True, secours=secours))
    elif not plan.mesures:
        page_vue["visuels"].append(
            {
                "fragile": False,
                "secours": "Pas de colonne numérique pour les barres.",
                "json": _texte(MARGE, y2, LARGEUR_UTILE, 160, "Aucune colonne numérique confirmée : les barres ne sont pas générées."),
            }
        )
    elif not plan.categorie_principale:
        if plan.date_pilote:
            page_vue["visuels"].append(_courbe(plan, MARGE, y2, LARGEUR_UTILE, h2))
        else:
            page_vue["visuels"].append(
                {
                    "fragile": False,
                    "secours": "Aucune catégorie confirmée.",
                    "json": _texte(MARGE, y2, LARGEUR_UTILE, 200, "Aucune catégorie confirmée : les barres ne sont pas générées."),
                }
            )

    # Évolution : grande courbe à gauche, indicateurs et filtre de dates à droite.
    page_evo = {"nom": "Évolution", "visuels": [_titre_page("Évolution")]}
    if plan.date_pilote and plan.mesures:
        largeur = LARGEUR_UTILE - COLONNE_DROITE - GOUTTIERE
        x_droite = MARGE + largeur + GOUTTIERE
        page_evo["visuels"].append(_courbe(plan, MARGE, HAUT_CONTENU, largeur, HAUTEUR_UTILE))
        page_evo["visuels"].append(_carte("Cumul annuel", "Cumul annuel", x_droite, HAUT_CONTENU, COLONNE_DROITE, 112))
        page_evo["visuels"].append(
            _carte("Vs mois precedent", "Vs mois precedent", x_droite, HAUT_CONTENU + 112 + GOUTTIERE, COLONNE_DROITE, 112)
        )
        y_segment = HAUT_CONTENU + 2 * (112 + GOUTTIERE)
        page_evo["visuels"].append(
            _segment(
                "Calendrier",
                "Date",
                "Date",
                x_droite,
                y_segment,
                COLONNE_DROITE,
                HAUTEUR - MARGE - y_segment,
                "Segment de dates à poser sur Calendrier[Date].",
            )
        )
    else:
        page_evo["visuels"].append(
            _message(
                "Pas de date pilote ou pas de mesure : la page d'évolution n'a pas de courbe. Le calendrier n'est pas créé.",
                "Pas de page chiffrée d'évolution.",
            )
        )

    # Répartitions : classement et parts côte à côte.
    page_rep = {"nom": "Répartitions", "visuels": [_titre_page("Répartitions")]}
    if plan.categorie_secondaire and plan.mesures:
        table, colonne = plan.categorie_secondaire
        mesure = f"Total {plan.mesures[0]}"
        (xa, wa), (xb, wb) = _colonnes(2)
        page_rep["visuels"].append(
            _barres(table, colonne, mesure, xa, HAUT_CONTENU, wa, HAUTEUR_UTILE, top=False, secours=f"Barres à poser : {table}[{colonne}] et {mesure}.")
        )
        page_rep["visuels"].append(
            # « Part du total » ne retire que le filtre de la catégorie principale : découpée par une
            # autre catégorie, chaque part vaudrait 100 %. L'anneau calcule lui-même les parts du Total.
            _anneau(
                table, colonne, xb, HAUT_CONTENU, wb, HAUTEUR_UTILE, "Anneau à poser : catégorie et Part du total.", mesure=mesure
            )
        )
    elif plan.categorie_principale and plan.mesures:
        table, colonne = plan.categorie_principale
        page_rep["visuels"].append(
            _anneau(table, colonne, MARGE, HAUT_CONTENU, LARGEUR_UTILE, HAUTEUR_UTILE, f"Anneau à poser : {table}[{colonne}] et Part du total.")
        )
    else:
        page_rep["visuels"].append(
            _message("Aucune catégorie confirmée : ni barres ni anneau.", "Pas de catégorie pour les répartitions.")
        )

    page_cor = {"nom": "Corrélations", "visuels": [_titre_page("Corrélations")]}
    if len(plan.mesures) >= 2:
        gauche, droite = (plan.paire_correlation[0], plan.paire_correlation[1]) if plan.paire_correlation else (plan.mesures[0], plan.mesures[1])
        roles = {
            "X": [_projection(_mesure(f"Total {gauche}"), f"Donnees.Total {gauche}")],
            "Y": [_projection(_mesure(f"Total {droite}"), f"Donnees.Total {droite}")],
        }
        if plan.categorie_principale:
            table, colonne = plan.categorie_principale
            roles["Category"] = [_projection(_colonne(table, colonne), f"{table}.{colonne}")]
        page_cor["visuels"].append(
            {
                "fragile": False,
                "secours": f"Nuage à poser : Total {gauche} et Total {droite}.",
                "json": _visuel("scatterChart", MARGE, HAUT_CONTENU, LARGEUR_UTILE, HAUTEUR_UTILE, f"{gauche} et {droite}", _requete(roles)),
            }
        )
    else:
        page_cor["visuels"].append(
            _message("Il faut deux colonnes numériques pour un nuage de points.", "Pas deux mesures pour un nuage.")
        )

    page_det = {"nom": "Détail", "visuels": [_titre_page("Détail")]}
    colonnes = [col for col in plan.colonnes_faits if plan.roles.get(col) != "ignoree"][:15]
    # Une clé étrangère cachée est lue depuis sa dimension.
    tables = {dimension.cle: dimension.nom for dimension in plan.dimensions}
    projections = [
        _projection(_colonne(tables.get(col, "Donnees"), col), f"{tables.get(col, 'Donnees')}.{col}") for col in colonnes
    ]
    segments = _segments(plan)
    largeur = LARGEUR_UTILE - COLONNE_DROITE - GOUTTIERE if segments else LARGEUR_UTILE
    page_det["visuels"].append(
        {
            "fragile": False,
            "secours": "Table à poser : " + ", ".join(colonnes) + ".",
            "json": _visuel("tableEx", MARGE, HAUT_CONTENU, largeur, HAUTEUR_UTILE, "Détail", _requete({"Values": projections})),
        }
    )
    if segments:
        hauteur = (HAUTEUR_UTILE - (len(segments) - 1) * GOUTTIERE) / len(segments)
        for index, (table, colonne) in enumerate(segments):
            page_det["visuels"].append(
                _segment(
                    table,
                    colonne,
                    colonne,
                    MARGE + largeur + GOUTTIERE,
                    HAUT_CONTENU + index * (hauteur + GOUTTIERE),
                    COLONNE_DROITE,
                    hauteur,
                    f"Segment à poser sur {table}[{colonne}].",
                )
            )
    return [page_vue, page_evo, page_rep, page_cor, page_det]


def _segments(plan: Plan) -> list[tuple[str, str]]:
    trouves = []
    for candidat in (plan.categorie_principale, plan.categorie_secondaire):
        if not candidat:
            continue
        table, colonne = candidat
        if plan.cardinalites.get(colonne, 99) <= 12:
            trouves.append((table, colonne))
    return trouves[:2]


def _coquille(theme: dict, pages: list[dict], avec_visuels: bool) -> dict[str, str]:
    identifiants = [identifiant_hex() for _ in pages]
    fichiers = {
        "definition.pbir": json.dumps(
            {
                "$schema": SCHEMAS["pbir"],
                "version": "4.0",
                "datasetReference": {"byPath": {"path": "../Rapport.SemanticModel"}},
            },
            ensure_ascii=False,
            indent=2,
        ),
        "definition/version.json": json.dumps(
            {"$schema": SCHEMAS["version"], "version": MANIFEST["versionContenu"]},
            ensure_ascii=False,
            indent=2,
        ),
        "definition/report.json": json.dumps(_report(theme), ensure_ascii=False, indent=2),
        "definition/pages/pages.json": json.dumps(
            {
                "$schema": SCHEMAS["pages"],
                "pageOrder": identifiants,
                "activePageName": identifiants[0],
            },
            ensure_ascii=False,
            indent=2,
        ),
        "StaticResources/RegisteredResources/theme.json": json.dumps(theme, ensure_ascii=False, indent=2),
    }
    for page, identifiant in zip(pages, identifiants):
        fichiers[f"definition/pages/{identifiant}/page.json"] = json.dumps(
            {
                "$schema": SCHEMAS["page"],
                "name": identifiant,
                "displayName": page["nom"],
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
            },
            ensure_ascii=False,
            indent=2,
        )
        if avec_visuels:
            for ordre, visuel in enumerate(page["gardes"]):
                visuel["position"]["z"] = ordre * 1000
                visuel["position"]["tabOrder"] = ordre * 1000
                fichiers[f"definition/pages/{identifiant}/visuals/{visuel['name']}/visual.json"] = json.dumps(
                    visuel, ensure_ascii=False, indent=2
                )
    return fichiers


def _report(theme: dict) -> dict:
    versions = {"visual": VERSIONS["visual"], "report": VERSIONS["report"], "page": VERSIONS["page"]}
    return {
        "$schema": SCHEMAS["report"],
        "themeCollection": {
            "baseTheme": {"name": MANIFEST["baseTheme"], "reportVersionAtImport": versions, "type": "SharedResources"},
            "customTheme": {
                "name": "theme.json",
                "reportVersionAtImport": versions,
                "type": "RegisteredResources",
            },
        },
        "resourcePackages": [
            {
                "name": "SharedResources",
                "type": "SharedResources",
                "items": [
                    {"name": MANIFEST["baseTheme"], "path": f"BaseThemes/{MANIFEST['baseTheme']}.json", "type": "BaseTheme"}
                ],
            },
            {
                "name": "RegisteredResources",
                "type": "RegisteredResources",
                "items": [{"name": "theme.json", "path": "theme.json", "type": "CustomTheme"}],
            },
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "defaultFilterActionIsDataFilter": True,
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "allowInlineExploration": True,
            "useEnhancedTooltips": True,
        },
    }


def _coquille_valide(fichiers: dict[str, str]) -> bool:
    attendus = {
        "definition.pbir": SCHEMAS["pbir"],
        "definition/version.json": SCHEMAS["version"],
        "definition/report.json": SCHEMAS["report"],
        "definition/pages/pages.json": SCHEMAS["pages"],
    }
    for chemin, schema in attendus.items():
        if erreurs(json.loads(fichiers[chemin]), schema):
            return False
    for chemin, contenu in fichiers.items():
        if chemin.endswith("page.json") and erreurs(json.loads(contenu), SCHEMAS["page"]):
            return False
    return True


def _resume(pages: list[dict]) -> list[dict]:
    resume = []
    for page in pages:
        champs = []
        for item in page["visuels"]:
            if item.get("titre"):
                continue  # le titre de page n'est pas un champ à poser
            secours = item["secours"]
            note = item.get("note")
            champs.append(secours if not note else f"{secours} {note}")
        resume.append({"nom": page["nom"], "champs": champs})
    return resume


def fichiers_projet(theme: dict) -> dict[str, str]:
    """Pointeurs PBIP et PBISM, validés contre les schémas vendored."""
    pbip = {
        "$schema": SCHEMAS["pbip"],
        "version": "1.0",
        "artifacts": [{"report": {"path": "Rapport.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }
    pbism = {"$schema": SCHEMAS["pbism"], "version": "5.0", "settings": {}}
    if erreurs(pbip, SCHEMAS["pbip"]) or erreurs(pbism, SCHEMAS["pbism"]):
        raise RuntimeError("Le gabarit PBIP ou PBISM ne passe pas son schéma.")
    return {
        "Rapport.pbip": json.dumps(pbip, ensure_ascii=False, indent=2) + "\n",
        "Rapport.SemanticModel/definition.pbism": json.dumps(pbism, ensure_ascii=False, indent=2) + "\n",
    }
