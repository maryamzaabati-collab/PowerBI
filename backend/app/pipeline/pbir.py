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


def _texte(x: float, y: float, w: float, h: float, texte: str) -> dict:
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
                                            "textStyle": {"fontFamily": "Segoe UI", "fontSize": "14px"},
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


def _pages(plan: Plan) -> list[dict]:
    cartes = [("Nombre de lignes", "Nombre de lignes de Donnees")]
    for colonne in plan.mesures[:3]:
        cartes.append((f"Total {colonne}", f"Mesure Total {colonne}"))
    page_vue = {"nom": "Vue d'ensemble", "visuels": []}
    for index, (mesure, libelle) in enumerate(cartes[:4]):
        page_vue["visuels"].append(
            {
                "fragile": False,
                "secours": f"Carte à poser : {libelle}.",
                "json": _visuel(
                    "card",
                    16 + index * 316,
                    16,
                    300,
                    120,
                    mesure,
                    _requete({"Values": [_projection(_mesure(mesure), f"Donnees.{mesure}")]}),
                ),
            }
        )
    if plan.categorie_principale and plan.mesures:
        table, colonne = plan.categorie_principale
        mesure = f"Total {plan.mesures[0]}"
        page_vue["visuels"].append(
            {
                "fragile": False,
                "topn": True,
                "secours": f"Barres groupées à poser : {table}[{colonne}] et {mesure}.",
                "json": _visuel(
                    "clusteredBarChart",
                    16,
                    156,
                    900,
                    540,
                    colonne,
                    _requete(
                        {
                            "Category": [_projection(_colonne(table, colonne), f"{table}.{colonne}")],
                            "Y": [_projection(_mesure(mesure), f"Donnees.{mesure}")],
                        },
                        tri=[{"field": _mesure(mesure), "direction": "Descending"}],
                    ),
                    filtre=_filtre_top(table, colonne),
                ),
            }
        )
        if plan.cardinalites.get(colonne, 99) <= 12:
            page_vue["visuels"].append(
                {
                    "fragile": True,
                    "secours": f"Segment à poser sur {table}[{colonne}].",
                    "json": _visuel(
                        "slicer",
                        936,
                        156,
                        320,
                        540,
                        colonne,
                        _requete({"Values": [_projection(_colonne(table, colonne), f"{table}.{colonne}")]}),
                    ),
                }
            )
    elif not plan.mesures:
        page_vue["visuels"].append(
            {
                "fragile": False,
                "secours": "Pas de colonne numérique pour les barres.",
                "json": _texte(16, 156, 1248, 160, "Aucune colonne numérique confirmée : les barres ne sont pas générées."),
            }
        )
    elif not plan.categorie_principale:
        page_vue["visuels"].append(
            {
                "fragile": False,
                "secours": "Aucune catégorie confirmée.",
                "json": _texte(16, 156, 1248, 200, "Aucune catégorie confirmée : les barres ne sont pas générées."),
            }
        )

    page_evo = {"nom": "Évolution", "visuels": []}
    if plan.date_pilote and plan.mesures:
        projections = [
            _projection(_mesure(f"Total {col}"), f"Donnees.Total {col}") for col in plan.mesures[:3]
        ]
        page_evo["visuels"].append(
            {
                "fragile": False,
                "secours": "Courbe à poser : Calendrier[Date] et les mesures Total.",
                "json": _visuel(
                    "lineChart",
                    16,
                    16,
                    900,
                    520,
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
        )
        page_evo["visuels"].append(
            {
                "fragile": False,
                "secours": "Carte à poser : Cumul annuel.",
                "json": _visuel(
                    "card",
                    936,
                    16,
                    320,
                    140,
                    "Cumul annuel",
                    _requete({"Values": [_projection(_mesure("Cumul annuel"), "Donnees.Cumul annuel")]}),
                ),
            }
        )
        page_evo["visuels"].append(
            {
                "fragile": True,
                "secours": "Segment de dates à poser sur Calendrier[Date].",
                "json": _visuel(
                    "slicer",
                    936,
                    176,
                    320,
                    360,
                    "Date",
                    _requete({"Values": [_projection(_colonne("Calendrier", "Date"), "Calendrier.Date")]}),
                ),
            }
        )
    else:
        page_evo["visuels"].append(
            {
                "fragile": False,
                "secours": "Pas de page chiffrée d'évolution.",
                "json": _texte(
                    16,
                    16,
                    1248,
                    200,
                    "Pas de date pilote ou pas de mesure : la page d'évolution n'a pas de courbe. Le calendrier n'est pas créé.",
                ),
            }
        )

    page_rep = {"nom": "Répartitions", "visuels": []}
    if plan.categorie_secondaire and plan.mesures:
        table, colonne = plan.categorie_secondaire
        mesure = f"Total {plan.mesures[0]}"
        page_rep["visuels"].append(
            {
                "fragile": False,
                "secours": f"Barres à poser : {table}[{colonne}] et {mesure}.",
                "json": _visuel(
                    "clusteredBarChart",
                    16,
                    16,
                    640,
                    640,
                    colonne,
                    _requete(
                        {
                            "Category": [_projection(_colonne(table, colonne), f"{table}.{colonne}")],
                            "Y": [_projection(_mesure(mesure), f"Donnees.{mesure}")],
                        }
                    ),
                ),
            }
        )
        page_rep["visuels"].append(
            {
                "fragile": False,
                "secours": "Anneau à poser : catégorie et Part du total.",
                "json": _visuel(
                    "donutChart",
                    680,
                    16,
                    560,
                    640,
                    "Part du total",
                    _requete(
                        {
                            "Category": [_projection(_colonne(table, colonne), f"{table}.{colonne}")],
                            "Y": [_projection(_mesure("Part du total"), "Donnees.Part du total")],
                        }
                    ),
                ),
            }
        )
    elif plan.categorie_principale and plan.mesures:
        table, colonne = plan.categorie_principale
        page_rep["visuels"].append(
            {
                "fragile": False,
                "secours": f"Anneau à poser : {table}[{colonne}] et Part du total.",
                "json": _visuel(
                    "donutChart",
                    16,
                    16,
                    1248,
                    640,
                    "Part du total",
                    _requete(
                        {
                            "Category": [_projection(_colonne(table, colonne), f"{table}.{colonne}")],
                            "Y": [_projection(_mesure("Part du total"), "Donnees.Part du total")],
                        }
                    ),
                ),
            }
        )
    else:
        page_rep["visuels"].append(
            {
                "fragile": False,
                "secours": "Pas de catégorie pour les répartitions.",
                "json": _texte(16, 16, 1248, 200, "Aucune catégorie confirmée : ni barres ni anneau."),
            }
        )

    page_cor = {"nom": "Corrélations", "visuels": []}
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
                "json": _visuel("scatterChart", 16, 16, 1248, 680, f"{gauche} et {droite}", _requete(roles)),
            }
        )
    else:
        page_cor["visuels"].append(
            {
                "fragile": False,
                "secours": "Pas deux mesures pour un nuage.",
                "json": _texte(16, 16, 1248, 200, "Il faut deux colonnes numériques pour un nuage de points."),
            }
        )

    page_det = {"nom": "Détail", "visuels": []}
    colonnes = [col for col in plan.colonnes_faits if plan.roles.get(col) != "ignoree"][:15]
    projections = [_projection(_colonne("Donnees", col), f"Donnees.{col}") for col in colonnes]
    page_det["visuels"].append(
        {
            "fragile": False,
            "secours": "Table à poser : " + ", ".join(colonnes) + ".",
            "json": _visuel(
                "tableEx",
                16,
                16,
                900 if _segments(plan) else 1248,
                688,
                "Détail",
                _requete({"Values": projections}),
            ),
        }
    )
    for index, (table, colonne) in enumerate(_segments(plan)):
        page_det["visuels"].append(
            {
                "fragile": True,
                "secours": f"Segment à poser sur {table}[{colonne}].",
                "json": _visuel(
                    "slicer",
                    936,
                    16 + index * 340,
                    320,
                    320,
                    colonne,
                    _requete({"Values": [_projection(_colonne(table, colonne), f"{table}.{colonne}")]}),
                ),
            }
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
            for visuel in page["gardes"]:
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
