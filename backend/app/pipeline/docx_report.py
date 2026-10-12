"""Compte rendu .docx. Les phrases viennent des chiffres pandas, pas d'un modèle de langage."""

from __future__ import annotations

import io
import re
from datetime import datetime

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

# Un code ou une coordonnée n'est pas une mesure à lire.
_CODE = re.compile(
    r"(?i)(?:^|_)(?:code|id|identifiant)(?:_|$)|latitude|longitude|^lat$|^lon$|postal"
)
_VOLUME = re.compile(r"(?i)volume|litre|quantit|poids|tonne|nombre de|nb_")
_PRIX = re.compile(r"(?i)prix|€\s*/\s*l|euros?")
_LITRE_EXPLICITE = re.compile(r"(?i)litre|€\s*/\s*l|/\s*l\b")
_CARDINALITE_MAX = 20
_PETIT_EFFECTIF = 5


def _nombre(valeur: float | int | None, decimales: int | None = None) -> str:
    if valeur is None or (isinstance(valeur, float) and pd.isna(valeur)):
        return "—"
    nombre = float(valeur)
    if decimales is None:
        if nombre.is_integer():
            texte = f"{int(round(nombre)):,}"
        else:
            texte = f"{nombre:,.2f}"
    else:
        texte = f"{nombre:,.{decimales}f}"
    return texte.replace(",", " ").replace(".", ",")


def _pct(valeur: float) -> str:
    return _nombre(valeur * 100) + " %"


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


def _figure(titre: str, dessin) -> io.BytesIO:
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


def _modalite(valeur: object) -> str:
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    texte = str(valeur).strip()
    if texte in {"True", "true"}:
        return "oui"
    if texte in {"False", "false"}:
        return "non"
    return texte


def _prix_au_litre(nom: str, mediane: float) -> bool:
    """Vrai seulement si le nom et l'ordre de grandeur disent un prix à l'unité litre."""
    if not _PRIX.search(nom):
        return False
    if _LITRE_EXPLICITE.search(nom):
        return 0 < mediane < 20
    return 0.3 <= mediane <= 6


def _mesures_qui_comptent(frame: pd.DataFrame, plan: Plan) -> tuple[list[dict], list[str]]:
    retenues = []
    ecartees = []
    for colonne in plan.mesures:
        if _CODE.search(colonne):
            ecartees.append(colonne)
            continue
        stats = _stats(frame[colonne]) if colonne in frame.columns else None
        if not stats:
            continue
        stats["nom"] = colonne
        stats["par_litre"] = _prix_au_litre(colonne, stats["mediane"])
        retenues.append(stats)
    retenues.sort(key=lambda item: (-item["n"], item["nom"]))
    return retenues, ecartees


def _categories_qui_comptent(frame: pd.DataFrame, plan: Plan) -> list[str]:
    retenues = []
    for colonne in frame.columns:
        role = plan.roles.get(colonne)
        if role not in {"categorie", "booleen", "geographique"}:
            continue
        card = int(frame[colonne].dropna().nunique())
        if 2 <= card <= _CARDINALITE_MAX:
            retenues.append(colonne)
    retenues.sort(key=lambda colonne: (int(frame[colonne].dropna().nunique()), colonne))
    return retenues[:4]


def _joindre(noms: list[str]) -> str:
    if not noms:
        return ""
    if len(noms) == 1:
        return noms[0]
    return ", ".join(noms[:-1]) + " et " + noms[-1]


def _niveau(valeur: float, par_litre: bool) -> str:
    if par_litre:
        return _nombre(valeur, 2) + " €/L"
    return _nombre(valeur)


def _phrase_plein(ecart: float) -> str:
    return f"soit {_nombre(ecart * 50, 2)} € pour 50 litres"


def _groupe(frame: pd.DataFrame, categorie: str, mesure: str) -> pd.DataFrame | None:
    if categorie not in frame.columns or mesure not in frame.columns:
        return None
    tableau = pd.DataFrame(
        {
            "modalite": frame[categorie].map(lambda valeur: None if pd.isna(valeur) else _modalite(valeur)),
            "valeur": pd.to_numeric(frame[mesure], errors="coerce"),
        }
    ).dropna()
    if tableau.empty:
        return None
    groupe = tableau.groupby("modalite")["valeur"].agg(moyenne="mean", effectif="count")
    if groupe.empty:
        return None
    return groupe.sort_values("moyenne", ascending=False)


def _frequence(frame: pd.DataFrame, categorie: str) -> tuple[str, int, float, int] | None:
    serie = frame[categorie].dropna().map(_modalite)
    if serie.empty:
        return None
    comptes = serie.value_counts()
    modalite = str(comptes.index[0])
    effectif = int(comptes.iloc[0])
    return modalite, effectif, effectif / max(len(frame), 1), int(frame[categorie].isna().sum())


def _comparables(mesures: list[dict]) -> list[dict]:
    au_litre = [item for item in mesures if item["par_litre"]]
    if len(au_litre) >= 2:
        return au_litre
    if len(mesures) < 2:
        return []
    reference = mesures[0]["mediane"] or mesures[0]["moyenne"]
    if reference == 0:
        return []
    proches = [
        item
        for item in mesures
        if item["mediane"] != 0 and 0.1 <= (item["mediane"] / reference) <= 10
    ]
    return proches if len(proches) >= 2 else []


def _ecart_mesures(mesures: list[dict]) -> dict | None:
    groupe = _comparables(mesures)
    if len(groupe) < 2:
        return None
    haute = max(groupe, key=lambda item: item["moyenne"])
    basse = min(groupe, key=lambda item: item["moyenne"])
    if haute["nom"] == basse["nom"]:
        return None
    return {
        "haute": haute,
        "basse": basse,
        "ecart": float(haute["moyenne"] - basse["moyenne"]),
        "par_litre": haute["par_litre"] and basse["par_litre"],
        "libelle": f"entre {haute['nom']} et {basse['nom']}",
    }


def _ecarts_categories(frame: pd.DataFrame, categories: list[str], mesure: dict) -> list[dict]:
    ecarts = []
    for categorie in categories:
        groupe = _groupe(frame, categorie, mesure["nom"])
        if groupe is None or len(groupe) < 2:
            continue
        haute = groupe.index[0]
        basse = groupe.index[-1]
        freq = _frequence(frame, categorie)
        ecarts.append(
            {
                "categorie": categorie,
                "mesure": mesure,
                "groupe": groupe,
                "haute": str(haute),
                "haute_moyenne": float(groupe.iloc[0]["moyenne"]),
                "haute_n": int(groupe.iloc[0]["effectif"]),
                "basse": str(basse),
                "basse_moyenne": float(groupe.iloc[-1]["moyenne"]),
                "basse_n": int(groupe.iloc[-1]["effectif"]),
                "ecart": float(groupe.iloc[0]["moyenne"] - groupe.iloc[-1]["moyenne"]),
                "frequence": freq,
                "vides": int(frame[categorie].isna().sum()),
            }
        )
    ecarts.sort(key=lambda item: item["ecart"], reverse=True)
    return ecarts


def _petit(effectif: int, lignes: int) -> bool:
    return effectif <= max(_PETIT_EFFECTIF, int(0.05 * lignes))


def _compte(nombre: int, singulier: str, pluriel: str | None = None) -> str:
    mot = singulier if int(nombre) == 1 else (pluriel or singulier + "s")
    return f"{_nombre(nombre)} {mot}"


def _phrase_mesure(item: dict, lignes: int) -> str:
    niveau = item["par_litre"]
    return (
        f"{item['nom']} : moyenne {_niveau(item['moyenne'], niveau)}, "
        f"minimum {_niveau(item['min'], niveau)}, maximum {_niveau(item['max'], niveau)}. "
        f"Couverture : {_compte(item['n'], 'valeur')} non vide"
        f"{'' if item['n'] == 1 else 's'} sur {_compte(lignes, 'ligne')}."
    )


def _phrase_ecart_mesures(ecart: dict) -> str:
    haute, basse = ecart["haute"], ecart["basse"]
    phrase = (
        f"Parmi ces mesures, la moyenne la plus haute est {haute['nom']} "
        f"({_niveau(haute['moyenne'], ecart['par_litre'])}) et la plus basse est {basse['nom']} "
        f"({_niveau(basse['moyenne'], ecart['par_litre'])}). "
        f"L'écart est de {_niveau(ecart['ecart'], ecart['par_litre'])}"
    )
    if ecart["par_litre"]:
        phrase += ", " + _phrase_plein(ecart["ecart"])
    return phrase + "."


def _phrase_categorie(ecart: dict, lignes: int) -> str:
    mesure = ecart["mesure"]
    niveau = mesure["par_litre"]
    phrase = (
        f"Selon {ecart['categorie']}, la moyenne de {mesure['nom']} va de "
        f"« {ecart['basse']} » ({_niveau(ecart['basse_moyenne'], niveau)}, "
        f"{_compte(ecart['basse_n'], 'ligne')}) à « {ecart['haute']} » "
        f"({_niveau(ecart['haute_moyenne'], niveau)}, {_compte(ecart['haute_n'], 'ligne')}). "
        f"L'écart est de {_niveau(ecart['ecart'], niveau)}"
    )
    if niveau:
        phrase += ", " + _phrase_plein(ecart["ecart"])
    phrase += "."
    if _petit(ecart["haute_n"], lignes) or _petit(ecart["basse_n"], lignes):
        phrase += " Une des deux modalités repose sur un petit effectif."
    freq = ecart["frequence"]
    if freq:
        modalite, effectif, part, _vides = freq
        phrase += (
            f" La modalité la plus fréquente de {ecart['categorie']} est « {modalite} » "
            f"({_compte(effectif, 'ligne')}, {_pct(part)})."
        )
    if ecart["vides"] == 1:
        phrase += f" 1 ligne n'a pas de {ecart['categorie']} et reste hors de cette comparaison."
    elif ecart["vides"]:
        phrase += (
            f" {_nombre(ecart['vides'])} lignes n'ont pas de {ecart['categorie']} "
            "et restent hors de cette comparaison."
        )
    return phrase


def _phrase_graphique_mesures(ecart: dict) -> str:
    return (
        f"On voit {ecart['haute']['nom']} au-dessus "
        f"({_niveau(ecart['haute']['moyenne'], ecart['par_litre'])}) et {ecart['basse']['nom']} en dessous "
        f"({_niveau(ecart['basse']['moyenne'], ecart['par_litre'])}). "
        f"L'écart entre les deux est de {_niveau(ecart['ecart'], ecart['par_litre'])}."
    )


def _phrase_graphique_categorie(ecart: dict) -> str:
    niveau = ecart["mesure"]["par_litre"]
    return (
        f"On voit « {ecart['haute']} » en haut "
        f"({_niveau(ecart['haute_moyenne'], niveau)}) et « {ecart['basse']} » en bas "
        f"({_niveau(ecart['basse_moyenne'], niveau)}). "
        f"L'écart est de {_niveau(ecart['ecart'], niveau)}."
    )


def _mensuel(frame: pd.DataFrame, date_col: str, mesure: str) -> pd.Series | None:
    if date_col not in frame.columns or mesure not in frame.columns:
        return None
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    valeurs = pd.to_numeric(frame[mesure], errors="coerce")
    tableau = pd.DataFrame({"date": dates, "valeur": valeurs}).dropna()
    if tableau.empty:
        return None
    return tableau.groupby(tableau["date"].dt.to_period("M"))["valeur"].mean()


def _conclusion(ecart_mesures: dict | None, ecarts_cat: list[dict]) -> str:
    candidats = []
    if ecart_mesures:
        candidats.append(
            (
                ecart_mesures["ecart"],
                ecart_mesures["par_litre"],
                f"l'écart entre les mesures {ecart_mesures['haute']['nom']} et {ecart_mesures['basse']['nom']}",
                ecart_mesures["ecart"],
            )
        )
    for ecart in ecarts_cat:
        candidats.append(
            (
                ecart["ecart"],
                ecart["mesure"]["par_litre"],
                f"l'écart de {ecart['mesure']['nom']} selon {ecart['categorie']}",
                ecart["ecart"],
            )
        )
    if not candidats:
        return "Aucun écart entre mesures ou entre modalités n'est lisible sur ce fichier."
    # On ne compare des écarts entre eux que lorsqu'ils sont dans la même unité.
    litres = [item for item in candidats if item[1]]
    pool = litres if len(litres) >= 2 or (len(litres) == 1 and not any(not item[1] for item in candidats)) else candidats
    if litres and any(not item[1] for item in candidats):
        pool = litres
    pool.sort(key=lambda item: item[0], reverse=True)
    premier = pool[0]
    phrase = (
        f"Ce qui pèse le plus dans les écarts observés est {premier[2]} "
        f"({_niveau(premier[0], premier[1])}"
    )
    if premier[1]:
        phrase += ", " + _phrase_plein(premier[0])
    phrase += ")."
    if len(pool) > 1:
        second = pool[1]
        phrase += f" Vient ensuite {second[2]} ({_niveau(second[0], second[1])})."
    phrase += " Rien dans ces chiffres n'établit la cause de l'écart."
    return phrase


def _limites(
    frame: pd.DataFrame,
    mesures: list[dict],
    ecarts_cat: list[dict],
    lignes: int,
) -> list[str]:
    phrases = []
    volumes = [colonne for colonne in frame.columns if _VOLUME.search(str(colonne))]
    if volumes:
        phrases.append(
            "Une colonne de volume ou de quantité existe ("
            + _joindre(volumes)
            + ") mais les moyennes ci-dessus ne sont pas pondérées par elle : chaque ligne pèse pareil."
        )
    else:
        phrases.append(
            "Pas de colonne de volume ou de quantité : chaque ligne pèse pareil dans les moyennes."
        )
    petits = []
    for ecart in ecarts_cat:
        for nom, effectif in ((ecart["haute"], ecart["haute_n"]), (ecart["basse"], ecart["basse_n"])):
            if _petit(effectif, lignes):
                petits.append(f"« {nom} » ({ecart['categorie']}, {_compte(effectif, 'ligne')})")
    if petits:
        phrases.append("Petits effectifs, à ne pas lire comme un résultat stable : " + _joindre(petits) + ".")
    phrases.append(
        "Les moyennes ne sont pas filtrées : elles prennent toutes les valeurs non vides, sans retirer une modalité ni un sous-ensemble."
    )
    partielles = [item for item in mesures if lignes and item["n"] < lignes * 0.5]
    if partielles:
        phrases.append(
            "Couverture faible : "
            + _joindre(
                f"{item['nom']} ({_nombre(item['n'])} valeurs sur {_nombre(lignes)})" for item in partielles
            )
            + "."
        )
    return phrases


def _entete_tableau(table, libelles: tuple[str, ...], accent: str) -> None:
    for cellule, libelle in zip(table.rows[0].cells, libelles):
        cellule.text = libelle
        _nuance(cellule, accent)
        for paragraphe in cellule.paragraphs:
            for run in paragraphe.runs:
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.bold = True


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
    couleurs = list(theme["dataColors"])
    accent = theme["tableAccent"]
    document = Document()
    document.core_properties.title = f"Compte rendu — {nom_fichier}"
    document.core_properties.language = "fr-FR"
    lignes = int(journal.get("lignes_apres", len(frame)))
    lues = int(profil.get("lignes", journal.get("lignes_avant", lignes)))

    titre = document.add_paragraph()
    titre.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = titre.add_run("Compte rendu")
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
        "Lecture des données",
        "Lecture des chiffres",
        "Graphiques",
        "Conclusion",
        "Limites",
        "Annexes",
    ):
        document.add_paragraph(libelle, style="List Number")
    note = document.add_paragraph()
    note.add_run(
        "Le champ ci-dessous est un sommaire Word. python-docx ne calcule pas les numéros de page : Word le met à jour à l'ouverture, parfois après confirmation. La liste ci-dessus reste lisible avant ça."
    )
    _sommaire_word(document.add_paragraph())

    mesures, ecartees = _mesures_qui_comptent(frame, plan)
    categories = _categories_qui_comptent(frame, plan)
    ecart_mesures = _ecart_mesures(mesures)
    principale = mesures[0] if mesures else None
    ecarts_cat = _ecarts_categories(frame, categories, principale) if principale else []

    document.add_heading("Lecture des données", level=1)
    identifiants = [
        colonne
        for colonne, role in plan.roles.items()
        if role == "identifiant" and colonne in frame.columns and frame[colonne].nunique(dropna=True) == lignes and lignes > 0
    ]
    if len(identifiants) == 1:
        document.add_paragraph(f"Une ligne = un enregistrement identifié par {identifiants[0]}.")
    else:
        document.add_paragraph("Une ligne = une observation du fichier.")
    document.add_paragraph(f"{_compte(lignes, 'ligne')} après nettoyage ({_compte(lues, 'ligne')} lues).")
    if mesures:
        document.add_paragraph("Les mesures qui comptent sont " + _joindre([item["nom"] for item in mesures]) + ".")
    else:
        document.add_paragraph("Aucune mesure numérique ne se prête à une lecture.")
    if categories:
        document.add_paragraph(
            "Les catégories qui comptent sont "
            + _joindre(categories)
            + ". Chacune a entre 2 et 20 modalités, ce qui permet de comparer."
        )
    else:
        document.add_paragraph("Aucune catégorie n'a entre 2 et 20 modalités : il n'y a pas de comparaison par groupe.")
    if ecartees:
        document.add_paragraph(
            "Ne comptent pas comme mesures : "
            + _joindre(ecartees)
            + ". Le nom indique un code ou une coordonnée, pas une grandeur à moyenner."
        )

    document.add_heading("Lecture des chiffres", level=1)
    if not mesures:
        document.add_paragraph("Sans mesure numérique, il n'y a ni moyenne, ni minimum, ni maximum à lire.")
    for item in mesures:
        document.add_paragraph(_phrase_mesure(item, lignes))
    if ecart_mesures:
        document.add_paragraph(_phrase_ecart_mesures(ecart_mesures))
    if not ecarts_cat and categories and principale:
        document.add_paragraph(
            f"Les catégories retenues n'opposent pas au moins deux modalités renseignées sur {principale['nom']}."
        )
    for ecart in ecarts_cat:
        document.add_paragraph(_phrase_categorie(ecart, lignes))

    document.add_heading("Graphiques", level=1)
    if ecart_mesures:
        ordre = sorted(_comparables(mesures), key=lambda item: item["moyenne"])

        def barres_mesures(ax, ordre=ordre):
            ax.barh(
                [item["nom"] for item in ordre],
                [item["moyenne"] for item in ordre],
                color=[couleurs[i % len(couleurs)] for i in range(len(ordre))],
            )
            ax.set_xlabel("Moyenne")

        document.add_picture(_figure("Moyenne des mesures", barres_mesures), width=Inches(6.2))
        document.add_paragraph(_phrase_graphique_mesures(ecart_mesures))
    for index, ecart in enumerate(ecarts_cat[:2]):
        groupe = ecart["groupe"].sort_values("moyenne")
        couleur = couleurs[index % len(couleurs)]

        def barres_cat(ax, groupe=groupe, couleur=couleur):
            ax.barh(list(groupe.index.astype(str)), list(groupe["moyenne"]), color=couleur)
            ax.set_xlabel(f"Moyenne de {ecart['mesure']['nom']}")

        document.add_picture(
            _figure(f"{ecart['mesure']['nom']} selon {ecart['categorie']}", barres_cat),
            width=Inches(6.2),
        )
        document.add_paragraph(_phrase_graphique_categorie(ecart))
    if plan.date_pilote and principale:
        serie = _mensuel(frame, plan.date_pilote, principale["nom"])
        if serie is not None and len(serie) >= 2:
            au_litre = principale["par_litre"]

            def courbe(ax, serie=serie):
                ax.plot(range(len(serie)), list(serie.values), color=couleurs[0], marker="o")
                ax.set_xticks(range(len(serie)))
                ax.set_xticklabels([str(v) for v in serie.index], rotation=35, ha="right")
                ax.set_ylabel("Moyenne")

            document.add_picture(
                _figure(f"Moyenne de {principale['nom']} par mois", courbe),
                width=Inches(6.2),
            )
            haut = serie.idxmax()
            bas = serie.idxmin()
            ecart_mois = float(serie.max() - serie.min())
            document.add_paragraph(
                f"On voit le mois le plus haut en {haut} ({_niveau(float(serie.max()), au_litre)}) "
                f"et le plus bas en {bas} ({_niveau(float(serie.min()), au_litre)}). "
                f"L'écart est de {_niveau(ecart_mois, au_litre)}."
            )
    if not ecart_mesures and not ecarts_cat and not (plan.date_pilote and principale):
        document.add_paragraph("Pas assez de mesures ou de catégories pour un graphique comparatif.")

    document.add_heading("Conclusion", level=1)
    document.add_paragraph(_conclusion(ecart_mesures, ecarts_cat))

    document.add_heading("Limites", level=1)
    for phrase in _limites(frame, mesures, ecarts_cat, lignes):
        document.add_paragraph(phrase)

    _annexes(
        document,
        frame,
        journal,
        profil,
        plan,
        accent,
        niveau,
        encodage,
        separateur_libelle,
        mesures,
        categories,
    )

    for section in document.sections:
        section.top_margin = Cm(1.6)
        section.bottom_margin = Cm(1.6)
        section.left_margin = Cm(1.6)
        section.right_margin = Cm(1.6)
    tampon = io.BytesIO()
    document.save(tampon)
    return tampon.getvalue()


def _annexes(
    document: Document,
    frame: pd.DataFrame,
    journal: dict,
    profil: dict,
    plan: Plan,
    accent: str,
    niveau: str,
    encodage: str,
    separateur_libelle: str,
    mesures: list[dict],
    categories: list[str],
) -> None:
    document.add_heading("Annexes", level=1)
    document.add_heading("Nettoyage", level=2)
    actives = [regle["libelle"] for regle in journal["regles"] if regle["active"]]
    inactives = [regle["libelle"] for regle in journal["regles"] if not regle["active"]]
    doublons = next((regle for regle in journal["regles"] if regle["id"] == "doublons" and regle["active"]), None)
    texte = (
        f"Fichier lu en {encodage}, séparateur {separateur_libelle}. "
        f"{_nombre(journal['lignes_avant'])} lignes avant nettoyage, {_nombre(journal['lignes_apres'])} après. "
        "Règles actives : " + (", ".join(actives) if actives else "aucune") + "."
    )
    if inactives:
        texte += " Désactivées : " + ", ".join(inactives) + "."
    if doublons and doublons["lignes_avant"] > doublons["lignes_apres"]:
        retires = doublons["lignes_avant"] - doublons["lignes_apres"]
        if retires == 1:
            texte += " 1 doublon de ligne a été retiré, la première occurrence est conservée."
        else:
            texte += (
                f" {_nombre(retires)} doublons de ligne ont été retirés, la première occurrence est conservée."
            )
    if journal.get("dates_ambigues"):
        texte += (
            " Dates ambiguës lues en jour/mois/année : " + ", ".join(journal["dates_ambigues"]) + "."
        )
    document.add_paragraph(texte)
    document.add_paragraph(
        "pandas calcule les chiffres de ce document. Le moteur Power Query n'est pas exécuté ici. "
        "Après actualisation, le modèle charge le CSV nettoyé, donc les mêmes lignes."
    )

    document.add_heading("Valeurs manquantes", level=2)
    incompletes = [col for col in journal["colonnes"] if col["manquants_apres"] > 0]
    incompletes.sort(key=lambda col: col["manquants_apres"], reverse=True)
    if not incompletes:
        document.add_paragraph("Aucune valeur manquante après nettoyage.")
    else:
        montre = incompletes[:12]
        table = document.add_table(rows=1, cols=2)
        table.style = "Table Grid"
        _entete_tableau(table, ("Colonne", "Part manquante"), accent)
        for col in montre:
            ligne = table.add_row().cells
            ligne[0].text = col["nom"]
            ligne[1].text = _pct(col["manquants_apres"])
        if len(incompletes) > len(montre):
            document.add_paragraph(
                f"{_nombre(len(incompletes) - len(montre))} autres colonnes ont aussi des manquants, sous la part de la dernière ligne affichée."
            )

    document.add_heading("Dictionnaire", level=2)
    document.add_paragraph("Mesures et catégories lues dans le corps du document. Le reste du fichier n'est pas redécrit ici.")
    dico = document.add_table(rows=1, cols=4)
    dico.style = "Table Grid"
    _entete_tableau(dico, ("Nom", "Rôle", "Cardinalité", "Valeurs non vides"), accent)
    profil_cols = {col["nom"]: col for col in profil.get("colonnes", [])}
    noms = [item["nom"] for item in mesures] + [col for col in categories if col not in {item["nom"] for item in mesures}]
    for nom in noms:
        info = profil_cols.get(nom, {})
        ligne = dico.add_row().cells
        ligne[0].text = nom
        ligne[1].text = plan.roles.get(nom, "")
        ligne[2].text = str(info.get("cardinalite", int(frame[nom].dropna().nunique()) if nom in frame.columns else ""))
        ligne[3].text = _nombre(int(frame[nom].notna().sum()) if nom in frame.columns else 0)

    document.add_heading("Formules DAX", level=2)
    for ligne in rendu_dax(plan).splitlines():
        document.add_paragraph(ligne)
    document.add_heading("Paramètre M", level=2)
    document.add_paragraph(
        "CheminFichierCsv est le paramètre du modèle et du script nettoyage.pq. Dans Transformer les données, Modifier les paramètres, indiquez le chemin absolu. Pour le modèle : donnees-nettoyees.csv. Pour rejouer le nettoyage sur le brut : source.csv."
    )
    if plan.mesures_non_generees:
        document.add_paragraph("Colonnes numériques sans mesure nommée : " + ", ".join(plan.mesures_non_generees) + ".")
    document.add_paragraph(
        f"Niveau PBIR obtenu : {niveau}. Un schéma valide ne prouve pas que Power BI Desktop affichera le visuel. Les données apparaissent dans Desktop après avoir renseigné CheminFichierCsv et actualisé."
    )
