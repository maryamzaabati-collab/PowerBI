"""Mesures DAX, les mêmes formules dans le fichier .dax et dans le TMDL."""

from __future__ import annotations

from backend.app.pipeline.modele import Plan
from backend.app.pipeline.naming import ref_dax


def _mesure(nom: str, expression: str, format_string: str, commentaire: str) -> dict:
    return {"nom": nom, "expression": expression, "format": format_string, "commentaire": commentaire}


def formules(plan: Plan) -> list[dict]:
    mesures: list[dict] = [
        _mesure(
            "Nombre de lignes",
            "COUNTROWS('Donnees')",
            "#,0",
            "Nombre de lignes de la table de faits après nettoyage.",
        )
    ]
    for colonne in plan.mesures:
        reference = ref_dax("Donnees", colonne)
        mesures.append(
            _mesure(
                f"Total {colonne}",
                f"SUM({reference})",
                "#,0.00",
                f"Somme de {colonne}. Aucune imputation : les vides ne comptent pas comme zéro.",
            )
        )
        mesures.append(
            _mesure(
                f"Moyenne {colonne}",
                f"AVERAGE({reference})",
                "#,0.00",
                f"Moyenne de {colonne}, sans les valeurs manquantes.",
            )
        )
    if not plan.mesures:
        return mesures + [
            {
                "nom": None,
                "expression": None,
                "format": None,
                "commentaire": "Pas de colonne numérique confirmée : seules les lignes sont comptées.",
            }
        ]
    principale = plan.mesures[0]
    total = f"[Total {principale}]"
    if plan.date_pilote:
        mesures.append(
            _mesure(
                "Vs mois precedent",
                "\n".join(
                    [
                        "VAR Courant = " + total,
                        "VAR Precedent =",
                        "    CALCULATE(",
                        "        " + total + ",",
                        "        DATEADD('Calendrier'[Date], -1, MONTH)",
                        "    )",
                        "RETURN",
                        "    DIVIDE(Courant - Precedent, Precedent)",
                    ]
                ),
                "0.00%",
                f"Écart relatif de {principale} par rapport au mois précédent, via le calendrier.",
            )
        )
        mesures.append(
            _mesure(
                "Cumul annuel",
                f"TOTALYTD({total}, 'Calendrier'[Date])",
                "#,0.00",
                f"Cumul annuel de {principale} sur la date du calendrier.",
            )
        )
    else:
        mesures.append(
            {
                "nom": None,
                "expression": None,
                "format": None,
                "commentaire": "Mesures temporelles absentes : aucune date pilote, donc pas de table Calendrier.",
            }
        )
    if plan.categorie_principale:
        table, colonne = plan.categorie_principale
        cible = ref_dax(table, colonne)
        mesures.append(
            _mesure(
                "Part du total",
                f"DIVIDE({total}, CALCULATE({total}, ALL({cible})))",
                "0.00%",
                f"Part de {principale} lorsque le filtre de {colonne} est retiré.",
            )
        )
        mesures.append(
            _mesure(
                "Rang",
                f"RANKX(ALL({cible}), {total}, , DESC, Dense)",
                "0",
                f"Rang de {colonne} selon {principale}. Le top 10 du visuel, lui, n'est pas garanti.",
            )
        )
    else:
        mesures.append(
            {
                "nom": None,
                "expression": None,
                "format": None,
                "commentaire": "Part du total et rang absents : aucune catégorie confirmée.",
            }
        )
    if plan.mesures_non_generees:
        liste = ", ".join(plan.mesures_non_generees)
        mesures.append(
            {
                "nom": None,
                "expression": None,
                "format": None,
                "commentaire": f"Mesures non générées au-delà de 8 colonnes : {liste}.",
            }
        )
    return mesures


def rendu(plan: Plan) -> str:
    lignes = [
        "// Mesures du modèle, culture fr-FR.",
        "// Les formules sont les mêmes que dans le TMDL.",
        "// Rien à coller si Rapport.pbip s'ouvre : elles sont déjà dans Donnees.",
        "",
    ]
    for mesure in formules(plan):
        lignes.append("// " + mesure["commentaire"])
        if mesure["nom"]:
            lignes.append(f"{mesure['nom']} =")
            for morceau in mesure["expression"].splitlines():
                lignes.append("    " + morceau)
            lignes.append("")
    return "\n".join(lignes).rstrip() + "\n"
