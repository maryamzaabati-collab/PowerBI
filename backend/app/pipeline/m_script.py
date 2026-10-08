"""Script M commenté en français, pour rejouer le nettoyage sur le CSV d'origine."""

from __future__ import annotations

import re

from backend.app.pipeline.naming import littéral_m

ENCODAGES = {"utf-8": 65001, "utf-8-sig": 65001, "cp1252": 1252, "latin-1": 28591}
ZERO_WIDTH = (160, 8203, 8204, 8205, 65279)


def identifiant_m(nom: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nom):
        return nom
    return '#"' + nom.replace('"', '""') + '"'


def champ_m(nom: str) -> str:
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", nom):
        return f"[{nom}]"
    return "[" + identifiant_m(nom) + "]"


def _delimiteur(sep: str) -> str:
    if sep == "\t":
        return '"#(tab)"'
    return littéral_m(sep)


def _liste_types(paires: list[tuple[str, str]], culture: str | None = None) -> str:
    corps = ", ".join(f"{{{littéral_m(nom)}, {type_m}}}" for nom, type_m in paires)
    if culture:
        return f"Table.TransformColumnTypes(Precedent, {{{corps}}}, {littéral_m(culture)})"
    return f"Table.TransformColumnTypes(Precedent, {{{corps}}})"


def script_nettoyage(
    renommage: list[dict],
    roles: dict,
    regles: dict,
    encodage: str,
    separateur: str,
) -> str:
    code = ENCODAGES.get(encodage, 65001)
    culture_nombres = "fr-FR" if separateur == ";" else "en-US"
    lignes = [
        "// Chemin absolu du CSV d'origine. Pas de chemin relatif fiable dans Power Query.",
        "// Collez ce script dans une requête vide pour rejouer le nettoyage sur un prochain extrait.",
        "// Le modèle, lui, lit donnees-nettoyees.csv : voir la partition de Donnees et le LISEZMOI.",
        "// Encodage détecté : " + encodage + f" (code {code}). Séparateur : {_libelle_sep(separateur)}.",
        "// Les dates ambiguës (jour et mois tous deux inférieurs ou égaux à 12) sont lues en jour/mois/année.",
        "let",
        "    // Étape : paramètre de chemin, à remplacer avant d'exécuter.",
        '    CheminFichierCsv = "C:\\\\REMPLACER\\\\source.csv",',
        "    // Étape : lecture du fichier d'origine.",
        "    Source = Csv.Document(",
        "        File.Contents(CheminFichierCsv),",
        f"        [Delimiter = {_delimiteur(separateur)}, Encoding = {code}, QuoteStyle = QuoteStyle.Csv]",
        "    ),",
        "    // Étape : promotion des en-têtes.",
        "    Entetes = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
    ]
    renoms = [(item["source"], item["modele"]) for item in renommage if item["source"] != item["modele"]]
    if renoms:
        paires = ", ".join(f"{{{littéral_m(src)}, {littéral_m(dst)}}}" for src, dst in renoms)
        lignes += [
            "    // Étape : noms du modèle, pour que l'en-tête coïncide avec sourceColumn.",
            f"    Renommes = Table.RenameColumns(Entetes, {{{paires}}}, MissingField.Ignore),",
        ]
        precedent = "Renommes"
    else:
        lignes.append("    // Étape : les noms d'en-tête sont déjà ceux du modèle.")
        precedent = "Entetes"

    def suite(nom: str, expression: str, commentaire: str) -> None:
        nonlocal precedent
        lignes.append(f"    // {commentaire}")
        lignes.append(f"    {nom} = {expression},")
        precedent = nom

    if regles.get("trim", True):
        transformations = []
        for item in renommage:
            nom = item["modele"]
            transformations.append("{" + littéral_m(nom) + ", " + _expression_trim(nom) + ", type text}")
        suite(
            "ApresTrim",
            "Table.TransformColumns(" + precedent + ", {" + ", ".join(transformations) + "})",
            "Étape : trim, espaces insécables et caractères de largeur nulle retirés.",
        )
    else:
        lignes.append("    // Étape non demandée : trim.")

    if regles.get("vides", True):
        colonnes = ", ".join(littéral_m(item["modele"]) for item in renommage)
        suite(
            "VidesEnNull",
            f'Table.ReplaceValue({precedent}, "", null, Replacer.ReplaceValue, {{{colonnes}}})',
            "Étape : chaîne vide devenue manquante. Aucune imputation par zéro.",
        )
    else:
        lignes.append("    // Étape non demandée : vides devenus manquants.")

    if regles.get("doublons", True):
        suite(
            "SansDoublons",
            f"Table.Distinct({precedent})",
            "Étape : doublons de ligne exacts, la première occurrence est conservée.",
        )
    else:
        lignes.append("    // Étape non demandée : suppression des doublons.")

    categories = [nom for nom, role in roles.items() if role == "categorie"]
    if regles.get("casse"):
        if categories:
            for nom in categories:
                suite(
                    "Casse_" + _suffixe(nom),
                    _expression_casse(precedent, nom),
                    f"Étape : casse de {nom}. La graphie la plus fréquente remplace les variantes. Jamais sur un identifiant.",
                )
        else:
            lignes.append("    // Étape casse demandée, mais aucune colonne de catégorie n'est confirmée.")
    else:
        lignes.append("    // Étape non demandée : harmonisation de la casse.")

    if regles.get("nombres", True):
        cibles = [
            (nom, "Int64.Type")
            for nom, role in roles.items()
            if role == "numerique"
        ]
        # Le script M ne sait pas, colonne par colonne, si la partie décimale existe.
        # On pose type number ; le CSV nettoyé, lui, a déjà choisi entier ou décimal.
        cibles = [(nom, "type number") for nom, _ in cibles]
        geo = [nom for nom, role in roles.items() if role == "geographique" and _est_coordonnee(nom)]
        cibles += [(nom, "type number") for nom in geo]
        if cibles:
            suite(
                "Nombres",
                _liste_types(cibles, culture_nombres).replace("Precedent", precedent),
                "Étape : nombres. Culture "
                + culture_nombres
                + ". Une cellule non parsable devient nulle. Si le point et la virgule coexistent, pandas a tranché à la génération ; ce script utilise une culture par colonne.",
            )
        else:
            lignes.append("    // Étape nombres demandée, mais aucune colonne numérique n'est confirmée.")
    else:
        lignes.append("    // Étape non demandée : conversion des nombres.")

    if regles.get("dates", True):
        cibles = [(nom, "type date") for nom, role in roles.items() if role == "temporel"]
        if cibles:
            suite(
                "Dates",
                _liste_types(cibles, "fr-FR").replace("Precedent", precedent),
                "Étape : dates en culture fr-FR, donc jour/mois/année. Sortie date. Les valeurs ambiguës restent signalées dans le journal, pas ici.",
            )
        else:
            lignes.append("    // Étape dates demandée, mais aucune colonne temporelle n'est confirmée.")
    else:
        lignes.append("    // Étape non demandée : conversion des dates.")

    lignes.append("    // Les valeurs aberrantes sont signalées dans le compte rendu. Elles ne sont pas supprimées.")
    lignes.append(f"    Resultat = {precedent}")
    lignes.append("in")
    lignes.append("    Resultat")
    return "\n".join(lignes) + "\n"


def script_partition(colonnes: list[tuple[str, str]]) -> str:
    """Lecture typée du CSV déjà nettoyé. Pas les règles de nettoyage."""
    types = ", ".join(f"{{{littéral_m(nom)}, {type_m}}}" for nom, type_m in colonnes)
    return "\n".join(
        [
            "let",
            "    // CSV nettoyé par pandas, UTF-8, virgule, point décimal, dates AAAA-MM-JJ.",
            "    // Remplacez CheminFichierCsv par le chemin absolu de donnees-nettoyees.csv.",
            "    Source = Csv.Document(",
            "        File.Contents(CheminFichierCsv),",
            '        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]',
            "    ),",
            "    Entetes = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
            f'    Types = Table.TransformColumnTypes(Entetes, {{{types}}}, "en-US")',
            "in",
            "    Types",
        ]
    )


def script_dimension(colonnes: list[str], cle: str) -> str:
    projection = ", ".join(littéral_m(nom) for nom in colonnes)
    types = ", ".join(
        f"{{{littéral_m(nom)}, type text}}" for nom in colonnes
    )
    return "\n".join(
        [
            "let",
            "    Source = Csv.Document(",
            "        File.Contents(CheminFichierCsv),",
            '        [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]',
            "    ),",
            "    Entetes = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),",
            f"    Colonnes = Table.SelectColumns(Entetes, {{{projection}}}),",
            f'    Types = Table.TransformColumnTypes(Colonnes, {{{types}}}, "en-US"),',
            f"    // Une ligne par identifiant. En cas de conflit, la première graphie est gardée.",
            f"    Distincts = Table.Distinct(Types, {{{littéral_m(cle)}}})",
            "in",
            "    Distincts",
        ]
    )


def _expression_trim(_nom: str) -> str:
    # Table.TransformColumns passe la cellule dans `_`, pas la ligne.
    corps = "_"
    for code in ZERO_WIDTH:
        corps = f"Text.Replace({corps}, Character.FromNumber({code}), \" \")"
    return f"each if _ = null then null else Text.Trim({corps})"


def _expression_casse(precedent: str, nom: str) -> str:
    cle = champ_m(nom)
    return "\n".join(
        [
            "let",
            f"        AvecCle = Table.AddColumn({precedent}, \"_cle_casse\", each if {cle} = null then null else Text.Lower(Text.From({cle}))),",
            "        Comptage = Table.Group(",
            "            Table.SelectRows(AvecCle, each [_cle_casse] <> null),",
            "            {\"_cle_casse\", " + littéral_m(nom) + "},",
            "            {{\"N\", each Table.RowCount(_), Int64.Type}}",
            "        ),",
            "        Tri = Table.Sort(Comptage, {{\"N\", Order.Descending}}),",
            "        Choix = Table.Distinct(Tri, {\"_cle_casse\"}),",
            "        Joint = Table.NestedJoin(AvecCle, {\"_cle_casse\"}, Choix, {\"_cle_casse\"}, \"_ref\", JoinKind.LeftOuter),",
            "        Developpe = Table.ExpandTableColumn(Joint, \"_ref\", {" + littéral_m(nom) + "}, {\"_graphie\"}),",
            f"        Remplace = Table.AddColumn(Developpe, \"_nouveau\", each if [_graphie] = null then {cle} else [_graphie]),",
            "        Nettoye = Table.RenameColumns(Table.RemoveColumns(Remplace, {"
            + littéral_m(nom)
            + ", \"_cle_casse\", \"_graphie\"}), {{\"_nouveau\", "
            + littéral_m(nom)
            + "}})",
            "    in",
            "        Nettoye",
        ]
    )


def _suffixe(nom: str) -> str:
    propre = re.sub(r"[^A-Za-z0-9_]", "_", nom)
    return propre or "Colonne"


def _est_coordonnee(nom: str) -> bool:
    from backend.app.pipeline.naming import cle_nom

    return cle_nom(nom) in {"lat", "latitude", "lon", "longitude"}


def _libelle_sep(sep: str) -> str:
    return {";": "point-virgule", ",": "virgule", "\t": "tabulation", "|": "barre verticale"}.get(sep, sep)


def type_m_pour(type_apres: str) -> str:
    return {
        "entier": "Int64.Type",
        "décimal": "type number",
        "date": "type date",
        "booléen": "type logical",
        "vide": "type text",
        "texte": "type text",
    }.get(type_apres, "type text")
