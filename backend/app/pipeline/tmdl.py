"""Modèle TMDL : Donnees, Calendrier calculé, dimensions préfixées."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from backend.app.pipeline.dax import formules
from backend.app.pipeline.m_script import script_dimension, script_partition, type_m_pour
from backend.app.pipeline.modele import Plan
from backend.app.pipeline.naming import nom_tmdl, ref_colonne_tmdl, ref_dax

MANIFEST = json.loads(
    (Path(__file__).resolve().parents[2] / "templates" / "pbip" / "manifest.json").read_text(encoding="utf-8")
)

TYPES = {
    "entier": "int64",
    "décimal": "double",
    "date": "dateTime",
    "booléen": "boolean",
    "texte": "string",
    "vide": "string",
}
FORMATS = {
    "entier": "0",
    "décimal": "#,0.00",
    "date": "yyyy-MM-dd",
}


def _guid() -> str:
    return str(uuid.uuid4())


def _types_journal(journal: dict) -> dict[str, str]:
    return {col["nom"]: col["type_apres"] for col in journal["colonnes"]}


def _colonne(
    nom: str,
    type_apres: str,
    *,
    masquer: bool = False,
    cle: bool = False,
    tri: str | None = None,
    mesure: bool = False,
) -> str:
    data_type = TYPES.get(type_apres, "string")
    lignes = [f"\tcolumn {nom_tmdl(nom)}", f"\t\tdataType: {data_type}"]
    if cle:
        lignes.append("\t\tisKey")
    if type_apres in FORMATS:
        lignes.append(f"\t\tformatString: {json.dumps(FORMATS[type_apres])}")
    lignes.append(f"\t\tlineageTag: {_guid()}")
    # Les mesures explicites portent l'agrégation. summarizeBy none sur les mesures.
    if mesure or data_type in {"string", "dateTime", "boolean"}:
        lignes.append("\t\tsummarizeBy: none")
    lignes.append(f"\t\tsourceColumn: {nom_tmdl(nom)}")
    if tri:
        lignes.append(f"\t\tsortByColumn: {nom_tmdl(tri)}")
    if masquer:
        lignes.append("\t\tisHidden")
    lignes.append("")
    lignes.append("\t\tannotation SummarizationSetBy = Automatic")
    return "\n".join(lignes)


def _mesure_tmdl(mesure: dict) -> str:
    if not mesure["nom"]:
        return f"\t/// {mesure['commentaire']}"
    lignes = [f"\t/// {mesure['commentaire']}"]
    if "\n" in mesure["expression"]:
        lignes.append(f"\tmeasure {nom_tmdl(mesure['nom'])} = ```")
        lignes.extend(f"\t\t\t{morceau}" for morceau in mesure["expression"].splitlines())
        lignes.append("\t\t\t```")
    else:
        lignes.append(f"\tmeasure {nom_tmdl(mesure['nom'])} = {mesure['expression']}")
    lignes.append(f"\t\tformatString: {json.dumps(mesure['format'])}")
    lignes.append("\t\tdisplayFolder: Mesures")
    lignes.append(f"\t\tlineageTag: {_guid()}")
    return "\n".join(lignes)


def _partition_m(nom: str, script: str) -> str:
    lignes = [f"\tpartition {nom_tmdl(nom)} = m", "\t\tmode: import", "\t\tsource ="]
    lignes.extend("\t\t\t" + morceau for morceau in script.splitlines())
    return "\n".join(lignes)


def _partition_dax(nom: str, dax: str) -> str:
    lignes = [f"\tpartition {nom_tmdl(nom)} = calculated", "\t\tmode: import", "\t\tsource = ```"]
    lignes.extend("\t\t\t" + morceau for morceau in dax.splitlines())
    lignes.append("\t\t\t```")
    return "\n".join(lignes)


def _calendrier_dax(plan: Plan) -> str:
    date_ref = ref_dax("Donnees", plan.date_pilote or "Date")
    return "\n".join(
        [
            "VAR DateMin = MIN(" + date_ref + ")",
            "VAR DateMax = MAX(" + date_ref + ")",
            "RETURN",
            "ADDCOLUMNS(",
            "    CALENDAR(DATE(YEAR(DateMin), 1, 1), DATE(YEAR(DateMax), 12, 31)),",
            '    "Année", YEAR([Date]),',
            '    "Trimestre", "T" & FORMAT([Date], "Q"),',
            '    "Mois", MONTH([Date]),',
            '    "Nom du mois", FORMAT([Date], "MMMM", "fr-FR"),',
            '    "Année-Mois", FORMAT([Date], "YYYY-MM")',
            ")",
        ]
    )


def _relation(depuis_table: str, depuis_col: str, vers_table: str, vers_col: str) -> str:
    return "\n".join(
        [
            f"relationship {_guid()}",
            "\tcrossFilteringBehavior: oneDirection",
            "\tfromCardinality: many",
            f"\tfromColumn: {ref_colonne_tmdl(depuis_table, depuis_col)}",
            "\ttoCardinality: one",
            f"\ttoColumn: {ref_colonne_tmdl(vers_table, vers_col)}",
        ]
    )


def generer_tmdl(plan: Plan, journal: dict) -> dict[str, str]:
    types = _types_journal(journal)
    roles = plan.roles
    fichiers: dict[str, str] = {}
    fichiers["definition/database.tmdl"] = "\n".join(
        [
            "database Database",
            f"\tcompatibilityLevel: {MANIFEST['compatibilityLevel']}",
            "\tcompatibilityMode: powerBI",
            "",
        ]
    )
    tables = ["Donnees"]
    if plan.date_pilote:
        tables.append("Calendrier")
    tables.extend(dim.nom for dim in plan.dimensions)
    ordre = ", ".join(json.dumps(nom) for nom in tables)
    modele = [
        "model Model",
        "\tculture: fr-FR",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: fr-FR",
        "\tdataAccessOptions",
        "\t\tlegacyRedirects",
        "\t\treturnErrorValuesAsNull",
        "",
        f"annotation PBI_QueryOrder = [{ordre}]",
        "",
        "annotation __PBI_TimeIntelligenceEnabled = " + ("1" if plan.date_pilote else "0"),
        "",
    ]
    # discourageImplicitMeasures n'est pas posé : il reste faux.
    for nom in tables:
        modele.append(f"ref table {nom_tmdl(nom)}")
    modele.append("ref expression CheminFichierCsv")
    modele.append("")
    fichiers["definition/model.tmdl"] = "\n".join(modele)

    relations = []
    if plan.date_pilote:
        relations.append(_relation("Donnees", plan.date_pilote, "Calendrier", "Date"))
    for dimension in plan.dimensions:
        relations.append(_relation("Donnees", dimension.cle, dimension.nom, dimension.cle))
    if relations:
        fichiers["definition/relationships.tmdl"] = "\n\n".join(relations) + "\n"
    else:
        fichiers["definition/relationships.tmdl"] = "/// Aucune relation : pas de date pilote et pas de dimension extraite.\n"

    fichiers["definition/expressions.tmdl"] = "\n".join(
        [
            "expression CheminFichierCsv =",
            '\t\t"C:\\\\REMPLACER\\\\donnees-nettoyees.csv" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
            f"\tlineageTag: {_guid()}",
            "",
            "\tannotation PBI_ResultType = Text",
            "",
        ]
    )

    colonnes_m = [(col, type_m_pour(types.get(col, "texte"))) for col in plan.colonnes_faits]
    corps = [
        "table Donnees",
        f"\tlineageTag: {_guid()}",
        "",
    ]
    for mesure in formules(plan):
        corps.append(_mesure_tmdl(mesure))
        corps.append("")
    for col in plan.colonnes_faits:
        corps.append(
            _colonne(
                col,
                types.get(col, "texte"),
                masquer=roles.get(col) == "ignoree",
                mesure=roles.get(col) == "numerique",
            )
        )
        corps.append("")
    corps.append(_partition_m("Donnees", script_partition(colonnes_m)))
    corps.append("")
    fichiers["definition/tables/Donnees.tmdl"] = "\n".join(corps)

    if plan.date_pilote:
        calendrier = [
            "table Calendrier",
            "\tdataCategory: Time",
            f"\tlineageTag: {_guid()}",
            "",
            _colonne("Date", "date", cle=True),
            "",
            _colonne("Année", "entier"),
            "",
            _colonne("Trimestre", "texte"),
            "",
            _colonne("Mois", "entier"),
            "",
            _colonne("Nom du mois", "texte", tri="Mois"),
            "",
            _colonne("Année-Mois", "texte"),
            "",
            _partition_dax("Calendrier", _calendrier_dax(plan)),
            "",
        ]
        fichiers["definition/tables/Calendrier.tmdl"] = "\n".join(calendrier)

    for dimension in plan.dimensions:
        bloc = [
            f"table {nom_tmdl(dimension.nom)}",
            f"\tlineageTag: {_guid()}",
            "",
        ]
        for col in dimension.colonnes:
            bloc.append(_colonne(col, "texte", cle=col == dimension.cle))
            bloc.append("")
        bloc.append(_partition_m(dimension.nom, script_dimension(dimension.colonnes, dimension.cle)))
        bloc.append("")
        fichiers[f"definition/tables/{dimension.nom}.tmdl"] = "\n".join(bloc)
    return fichiers
