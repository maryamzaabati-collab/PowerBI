"""Assemblage du ZIP. Les noms internes sont fixes."""

from __future__ import annotations

import io
import json
import zipfile

import pandas as pd

from backend.app.pipeline.clean import ecrire_csv
from backend.app.pipeline.dax import rendu as rendu_dax
from backend.app.pipeline.docx_report import construire_docx
from backend.app.pipeline.m_script import script_nettoyage
from backend.app.pipeline.modele import Plan, construire_plan
from backend.app.pipeline.pbir import fichiers_projet, generer_pbir
from backend.app.pipeline.tmdl import generer_tmdl


def produire(contexte: dict, avancer=None) -> tuple[bytes, dict]:
    def etape(nom: str) -> None:
        if avancer:
            avancer(nom)

    frame: pd.DataFrame = contexte["nettoye"]
    etape("preparation")
    plan: Plan = construire_plan(frame, contexte["roles"], contexte["date_pilote"])
    journal = dict(contexte["journal"])
    journal["encodage"] = contexte["encodage"]
    journal["separateur"] = contexte["separateur"]
    journal["fichier"] = contexte["nom_fichier"]
    dax = rendu_dax(plan)
    pq = script_nettoyage(
        contexte["renommage"],
        contexte["roles"],
        contexte["regles"],
        contexte["encodage"],
        contexte["separateur"],
    )
    etape("tmdl")
    tmdl = generer_tmdl(plan, journal)
    etape("pbir")
    rapport = generer_pbir(plan, contexte["theme"])
    etape("compte_rendu")
    docx = construire_docx(
        contexte["nom_fichier"],
        frame,
        journal,
        contexte["profil"],
        plan,
        contexte["theme"],
        rapport["niveau"],
        contexte["encodage"],
        contexte["separateur_libelle"],
    )
    etape("zip")
    lisezmoi = _lisezmoi(contexte, plan, rapport)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr("LISEZMOI.txt", lisezmoi)
        zipf.writestr("donnees/source.csv", contexte["source"])
        zipf.writestr("donnees/donnees-nettoyees.csv", _csv_bytes(frame))
        zipf.writestr("donnees/journal.json", json.dumps(journal, ensure_ascii=False, indent=2, default=str))
        zipf.writestr("power-query/nettoyage.pq", pq)
        zipf.writestr("dax/mesures.dax", dax)
        zipf.writestr("theme/theme.json", json.dumps(contexte["theme"], ensure_ascii=False, indent=2))
        zipf.writestr("compte-rendu.docx", docx)
        for chemin, contenu in fichiers_projet(contexte["theme"]).items():
            zipf.writestr(chemin, contenu)
        for chemin, contenu in tmdl.items():
            zipf.writestr(f"Rapport.SemanticModel/{chemin}", contenu)
        for chemin, contenu in rapport["fichiers"].items():
            zipf.writestr(f"Rapport.Report/{chemin}", contenu)
    return archive.getvalue(), {
        "niveau": rapport["niveau"],
        "detail": rapport["detail"],
        "pages": rapport["pages"],
        "plan_mesures": plan.mesures,
        "date_pilote": plan.date_pilote,
    }


def _csv_bytes(frame: pd.DataFrame) -> bytes:
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temporaire:
        chemin = Path(temporaire.name)
    try:
        ecrire_csv(frame, chemin)
        return chemin.read_bytes()
    finally:
        chemin.unlink(missing_ok=True)


def _lisezmoi(contexte: dict, plan: Plan, rapport: dict) -> str:
    pages = []
    for page in rapport["pages"]:
        pages.append(page["nom"])
        for champ in page["champs"]:
            pages.append("  - " + champ)
    dimensions = ", ".join(dim.nom for dim in plan.dimensions) or "aucune"
    return "\n".join(
        [
            "Pack Power BI local",
            "",
            f"Fichier d'origine : {contexte['nom_fichier']}",
            f"Niveau du rapport : {rapport['niveau']}",
            rapport["detail"],
            "",
            "Ce pack a été produit sur la machine qui a lancé l'outil.",
            "Aucune ligne n'a été envoyée à un service d'analyse, à un géocodeur ou à un modèle de langage.",
            "",
            "1. Ouvrir Rapport.pbip avec Power BI Desktop grand public (pas l'édition Report Server).",
            "   Un Desktop antérieur au format PBIR peut refuser le rapport. Le modèle TMDL, le M, le DAX,",
            "   le thème, le CSV et le compte rendu restent utilisables.",
            "2. Transformer les données → Modifier les paramètres → CheminFichierCsv.",
            "   Indiquez le chemin absolu de donnees/donnees-nettoyees.csv.",
            "   Exemple à remplacer : C:\\REMPLACER\\donnees-nettoyees.csv",
            "3. Actualiser. Le cache .pbi n'est pas dans ce ZIP : les visuels restent vides avant l'actualisation.",
            "4. Si les couleurs n'ont pas suivi : Affichage → Thèmes → Parcourir les thèmes → theme/theme.json.",
            "5. Si le niveau est B ou C : posez les visuels listés plus bas. Les mesures sont déjà dans Donnees.",
            "6. Si Desktop demande de confirmer que Calendrier est une table de dates, confirmez sur la colonne Date.",
            "   Le TMDL demande ce marquage (dataCategory: Time).",
            "7. Pour rejouer le nettoyage sur un brut : collez power-query/nettoyage.pq dans une requête vide",
            "   et visez donnees/source.csv avec le même paramètre CheminFichierCsv.",
            "8. À l'ouverture de compte-rendu.docx, mettez à jour les champs si Word le propose.",
            "",
            f"Date pilote : {plan.date_pilote or 'aucune'}.",
            f"Dimensions extraites : {dimensions}.",
            "Les autres catégories restent dans Donnees.",
            "",
            "Pages et champs prévus",
            *pages,
            "",
            "Le niveau A signifie que les visual.json passent les schémas JSON vendored.",
            "Il ne signifie pas que Power BI Desktop affichera ces visuels : cela n'a pas été ouvert ici.",
            "",
        ]
    )
