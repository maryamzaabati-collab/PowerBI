"""Compte rendu .docx. Les chiffres sont ceux de pandas."""

from __future__ import annotations

import io
from datetime import date, datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

from backend.app.pipeline.dax import rendu as rendu_dax
from backend.app.pipeline.modele import Plan


def _nombre(valeur: float | int | None) -> str:
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return "—"
    if isinstance(valeur, float) and not valeur.is_integer():
        texte = f"{valeur:,.2f}"
    else:
        texte = f"{int(round(float(valeur))):,}"
    return texte.replace(",", " ").replace(".", ",")


def _pct(valeur: float) -> str:
    return _nombre(valeur * 100).replace("—", "0") + " %"


def _nuance(cellule, hexa: str) -> None:
    pr = cellule._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hexa.lstrip("#"))
    pr.append(shd)


def _sommaire_word(paragraphe) -> None:
    run = paragraphe.add_run()
    debut = OxmlElement("w:fldChar")
    debut.set(qn("w:fldCharType"), "begin")
    instruction = OxmlElement("w:instrText")
    instruction.set(qn("xml:space"), "preserve")
    instruction.text = ' TOC \\o "1-2" \\h \\z \\u '
    separe = OxmlElement("w:fldChar")
    separe.set(qn("w:fldCharType"), "separate")
    fin = OxmlElement("w:fldChar")
    fin.set(qn("w:fldCharType"), "end")
    run._r.append(debut)
    run._r.append(instruction)
    run._r.append(separe)
    run._r.append(fin)


def _figure(couleurs: list[str], titre: str, dessin) -> io.BytesIO:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    dessin(ax)
    ax.set_title(titre)
    fig.tight_layout()
    tampon = io.BytesIO()
    fig.savefig(tampon, format="png", dpi=120)
    plt.close(fig)
    tampon.seek(0)
    return tampon


def _stats(serie: pd.Series) -> dict | None:
    nombres = pd.to_numeric(serie, errors="coerce").dropna()
    if nombres.empty:
        return None
    return {
        "n": int(nombres.shape[0]),
        "min": float(nombres.min()),
        "max": float(nombres.max()),
        "moyenne": float(nombres.mean()),
        "mediane": float(nombres.median()),
    }


def construire_docx(
    nom_fichier: str,
    frame: pd.DataFrame,
    journal: dict,
    profil: dict,
    plan: Plan,
    theme: dict,
    niveau: str,
    encodage: str,
    separateur_libelle: str,
) -> bytes:
    couleurs = theme["dataColors"]
    accent = theme["tableAccent"]
    document = Document()
    document.core_properties.title = f"Compte rendu — {nom_fichier}"
    document.core_properties.language = "fr-FR"

    titre = document.add_paragraph()
    titre.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = titre.add_run("Compte rendu de préparation")
    run.bold = True
    run.font.size = Pt(26)
    run.font.color.rgb = RGBColor(int(accent[1:3], 16), int(accent[3:5], 16), int(accent[5:7], 16))
    sous = document.add_paragraph()
    sous.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sous.add_run(f"{nom_fichier}\n{datetime.now().strftime('%d/%m/%Y %H:%M')}")
    bandeau = document.add_table(rows=1, cols=len(couleurs))
    for cellule, couleur in zip(bandeau.rows[0].cells, couleurs):
        _nuance(cellule, couleur)
        cellule.text = ""
    document.add_paragraph("")

    document.add_heading("Sommaire", level=1)
    for libelle in (
        "Contexte",
        "Méthodologie de nettoyage",
        "Analyse descriptive",
        "Graphiques",
        "Insights",
        "Limites",
        "Recommandations",
        "Annexes",
    ):
        document.add_paragraph(libelle, style="List Number")
    note = document.add_paragraph()
    note.add_run(
        "Le champ ci-dessous est un sommaire Word. python-docx ne calcule pas les numéros de page : Word le met à jour à l'ouverture, parfois après confirmation. La liste ci-dessus reste lisible avant ça."
    )
    _sommaire_word(document.add_paragraph())

    document.add_heading("Contexte", level=1)
    document.add_paragraph(f"Fichier : {nom_fichier}.")
    document.add_paragraph(
        f"{profil['lignes']} lignes lues, {journal['lignes_apres']} après nettoyage, {profil['colonnes_nombre']} colonnes."
    )
    document.add_paragraph(f"Encodage : {encodage}. Séparateur : {separateur_libelle}.")
    if plan.date_pilote:
        document.add_paragraph(f"Date qui pilote le calendrier : {plan.date_pilote}.")
    else:
        document.add_paragraph("Aucune date pilote : le modèle n'a pas de table Calendrier.")

    document.add_heading("Méthodologie de nettoyage", level=1)
    document.add_paragraph(
        "pandas applique les règles pour l'aperçu, le journal, le CSV nettoyé et les chiffres de ce document. Le moteur Power Query n'est pas exécuté ici."
    )
    for regle in journal["regles"]:
        etat = "activée" if regle["active"] else "désactivée"
        document.add_paragraph(
            f"{regle['libelle']} — {etat}. Lignes avant : {regle['lignes_avant']}. Lignes après : {regle['lignes_apres']}.",
            style="List Bullet",
        )
    if journal["dates_ambigues"]:
        document.add_paragraph(
            "Dates ambiguës (le jour et le mois sont tous deux inférieurs ou égaux à 12), lues en jour/mois/année : "
            + ", ".join(journal["dates_ambigues"])
            + "."
        )
    table = document.add_table(rows=1, cols=5)
    table.style = "Table Grid"
    entetes = ("Colonne", "Type avant", "Type après", "Manquants avant", "Manquants après")
    for cellule, libelle in zip(table.rows[0].cells, entetes):
        cellule.text = libelle
        _nuance(cellule, accent)
        for paragraphe in cellule.paragraphs:
            for run in paragraphe.runs:
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.bold = True
    for col in journal["colonnes"]:
        ligne = table.add_row().cells
        ligne[0].text = col["nom"]
        ligne[1].text = col["type_avant"]
        ligne[2].text = col["type_apres"]
        ligne[3].text = _pct(col["manquants_avant"])
        ligne[4].text = _pct(col["manquants_apres"])

    document.add_heading("Analyse descriptive", level=1)
    if not plan.mesures:
        document.add_paragraph("Aucune colonne numérique confirmée. Les mesures du modèle se limitent au nombre de lignes.")
    for colonne in plan.mesures:
        stats = _stats(frame[colonne])
        if not stats:
            document.add_paragraph(f"{colonne} : aucune valeur numérique après nettoyage.")
            continue
        document.add_paragraph(
            f"{colonne} — effectif {_nombre(stats['n'])}, minimum {_nombre(stats['min'])}, maximum {_nombre(stats['max'])}, moyenne {_nombre(stats['moyenne'])}, médiane {_nombre(stats['mediane'])}."
        )
    if plan.categorie_principale:
        _table, colonne = plan.categorie_principale
        document.add_paragraph(f"Top 10 de {colonne}.")
        comptes = frame[colonne].dropna().astype(str).value_counts().head(10)
        top = document.add_table(rows=1, cols=3)
        top.style = "Table Grid"
        for cellule, libelle in zip(top.rows[0].cells, ("Modalité", "Effectif", "Part")):
            cellule.text = libelle
            _nuance(cellule, accent)
        total = max(len(frame), 1)
        for modalite, effectif in comptes.items():
            ligne = top.add_row().cells
            ligne[0].text = str(modalite)
            ligne[1].text = _nombre(int(effectif))
            ligne[2].text = _pct(effectif / total)

    document.add_heading("Graphiques", level=1)
    manquants = sorted(
        ((col["nom"], col["manquants_apres"]) for col in journal["colonnes"]),
        key=lambda item: item[1],
        reverse=True,
    )[:20]

    def barres_manquants(ax):
        ax.barh([nom for nom, _ in manquants][::-1], [part * 100 for _, part in manquants][::-1], color=couleurs[0])
        ax.set_xlabel("Part de manquants (%)")

    document.add_picture(_figure(couleurs, "Part de valeurs manquantes", barres_manquants), width=Inches(6.2))
    if plan.categorie_principale:
        _table, colonne = plan.categorie_principale
        comptes = frame[colonne].dropna().astype(str).value_counts().head(10)

        def barres_cat(ax):
            ax.bar(range(len(comptes)), list(comptes.values), color=couleurs[min(1, len(couleurs) - 1)])
            ax.set_xticks(range(len(comptes)))
            ax.set_xticklabels([str(v)[:18] for v in comptes.index], rotation=35, ha="right")

        document.add_picture(_figure(couleurs, f"Top de {colonne}", barres_cat), width=Inches(6.2))
    if plan.date_pilote and plan.mesures:
        serie = _mensuel(frame, plan.date_pilote, plan.mesures[0])
        if serie is not None and not serie.empty:

            def courbe(ax):
                ax.plot(range(len(serie)), list(serie.values), color=couleurs[0], marker="o")
                ax.set_xticks(range(len(serie)))
                ax.set_xticklabels([str(v) for v in serie.index], rotation=35, ha="right")

            document.add_picture(
                _figure(couleurs, f"{plan.mesures[0]} par mois", courbe),
                width=Inches(6.2),
            )
    if plan.mesures:
        valeurs = pd.to_numeric(frame[plan.mesures[0]], errors="coerce").dropna()
        if not valeurs.empty:

            def histo(ax):
                ax.hist(valeurs, bins=min(20, max(5, int(valeurs.nunique()))), color=couleurs[min(2, len(couleurs) - 1)])

            document.add_picture(_figure(couleurs, f"Distribution de {plan.mesures[0]}", histo), width=Inches(6.2))

    document.add_heading("Insights", level=1)
    phrases = _insights(frame, journal, plan, profil)
    if not phrases:
        document.add_paragraph("Aucune des phrases modèles ne s'applique à ce fichier.")
    for phrase in phrases:
        document.add_paragraph(phrase)

    document.add_heading("Limites", level=1)
    document.add_paragraph(
        "Les corrélations sont descriptives. Une date ambiguë est signalée dans le journal et lue en jour/mois/année. Aucun géocodage n'est fait : une latitude et une longitude restent deux nombres, et le rapport ne contient pas de carte."
    )
    document.add_paragraph(
        "Le script M n'a pas été exécuté. Un écart de culture ou d'arrondi peut rester entre nettoyage.pq et pandas. Après actualisation, le modèle charge le CSV nettoyé, donc les mêmes lignes que ce compte rendu."
    )
    document.add_paragraph(
        f"Niveau PBIR obtenu : {niveau}. Un schéma valide ne prouve pas que Power BI Desktop affichera le visuel. Les données apparaissent dans Desktop après avoir renseigné CheminFichierCsv et actualisé."
    )

    document.add_heading("Recommandations", level=1)
    conseils = _recommandations(frame, journal, plan, profil)
    if not conseils:
        document.add_paragraph("Rien de particulier à signaler au-delà des limites ci-dessus.")
    for conseil in conseils:
        document.add_paragraph(conseil, style="List Bullet")

    document.add_heading("Annexes", level=1)
    document.add_heading("Dictionnaire", level=2)
    dico = document.add_table(rows=1, cols=4)
    dico.style = "Table Grid"
    for cellule, libelle in zip(dico.rows[0].cells, ("Nom du modèle", "Nom source", "Rôle", "Cardinalité")):
        cellule.text = libelle
        _nuance(cellule, accent)
    profil_cols = {col["nom"]: col for col in profil["colonnes"]}
    for col in journal["colonnes"]:
        info = profil_cols.get(col["nom"], {})
        ligne = dico.add_row().cells
        ligne[0].text = col["nom"]
        ligne[1].text = info.get("nom_source", col["nom"])
        ligne[2].text = col["role"]
        ligne[3].text = str(info.get("cardinalite", ""))
    document.add_heading("Formules DAX", level=2)
    for ligne in rendu_dax(plan).splitlines():
        document.add_paragraph(ligne)
    document.add_heading("Paramètre M", level=2)
    document.add_paragraph(
        "CheminFichierCsv est le paramètre du modèle et du script nettoyage.pq. Dans Transformer les données, Modifier les paramètres, indiquez le chemin absolu. Pour le modèle : donnees-nettoyees.csv. Pour rejouer le nettoyage sur le brut : source.csv."
    )
    if plan.mesures_non_generees:
        document.add_paragraph("Colonnes numériques sans mesure nommée : " + ", ".join(plan.mesures_non_generees) + ".")

    # Évite un style de tableau trop étroit sur la page de garde.
    for section in document.sections:
        section.top_margin = Cm(1.6)
        section.bottom_margin = Cm(1.6)
        section.left_margin = Cm(1.6)
        section.right_margin = Cm(1.6)
    tampon = io.BytesIO()
    document.save(tampon)
    return tampon.getvalue()


def _mensuel(frame: pd.DataFrame, date_col: str, mesure: str) -> pd.Series | None:
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    valeurs = pd.to_numeric(frame[mesure], errors="coerce")
    tableau = pd.DataFrame({"date": dates, "valeur": valeurs}).dropna()
    if tableau.empty:
        return None
    return tableau.groupby(tableau["date"].dt.to_period("M"))["valeur"].sum()


def _insights(frame: pd.DataFrame, journal: dict, plan: Plan, profil: dict) -> list[str]:
    phrases = []
    if plan.categorie_principale:
        _table, colonne = plan.categorie_principale
        comptes = frame[colonne].dropna().astype(str).value_counts()
        if not comptes.empty:
            modalite = str(comptes.index[0])
            part = comptes.iloc[0] / max(len(frame), 1)
            phrases.append(f"La modalité la plus fréquente de {colonne} est « {modalite} » ({_pct(part)} des lignes).")
    if plan.date_pilote and plan.mesures:
        serie = _mensuel(frame, plan.date_pilote, plan.mesures[0])
        if serie is not None and len(serie) >= 2:
            phrases.append(
                f"Sur {plan.mesures[0]}, le premier mois ({serie.index[0]}) vaut {_nombre(float(serie.iloc[0]))} et le dernier mois ({serie.index[-1]}) vaut {_nombre(float(serie.iloc[-1]))}."
            )
    incompletes = [col for col in journal["colonnes"] if col["manquants_apres"] > 0.05]
    if incompletes:
        pire = max(incompletes, key=lambda col: col["manquants_apres"])
        phrases.append(
            f"La colonne la plus incomplète est {pire['nom']} ({_pct(pire['manquants_apres'])} de manquants)."
        )
    if plan.paire_correlation:
        gauche, droite, valeur = plan.paire_correlation
        phrases.append(
            f"La paire {gauche} et {droite} a la corrélation de Pearson la plus élevée (|r| = {abs(valeur):.2f}). C'est une corrélation, pas un lien de cause à effet."
        )
    retires = next((regle for regle in journal["regles"] if regle["id"] == "doublons" and regle["active"]), None)
    if retires and retires["lignes_avant"] > retires["lignes_apres"]:
        phrases.append(
            f"{retires['lignes_avant'] - retires['lignes_apres']} doublons de ligne ont été retirés."
        )
    return phrases


def _recommandations(frame: pd.DataFrame, journal: dict, plan: Plan, profil: dict) -> list[str]:
    conseils = []
    elevees = [col for col in journal["colonnes"] if col["manquants_apres"] > 0.2]
    if elevees:
        pire = max(elevees, key=lambda col: col["manquants_apres"])
        conseils.append(
            f"La colonne {pire['nom']} dépasse 20 % de manquants : à traiter avant d'interpréter les totaux."
        )
    for col in journal["colonnes"]:
        if col["role"] != "identifiant":
            continue
        info = next((item for item in profil["colonnes"] if item["nom"] == col["nom"]), None)
        ratio = info["ratio_cardinalite"] if info else 1
        if ratio < 1:
            conseils.append(
                f"L'identifiant {col['nom']} n'est pas unique ({_pct(ratio)} de valeurs distinctes sur les lignes du profil)."
            )
    if len(plan.mesures) == 1:
        conseils.append("Une seule colonne de mesure est disponible : les comparaisons entre indicateurs sont limitées.")
    if plan.date_pilote:
        serie = _mensuel(frame, plan.date_pilote, plan.mesures[0]) if plan.mesures else None
        mois = 0 if serie is None else len(serie)
        if mois < 3:
            conseils.append("La série temporelle couvre moins de trois mois : le cumul et l'écart mensuel seront peu lisibles.")
    return conseils
