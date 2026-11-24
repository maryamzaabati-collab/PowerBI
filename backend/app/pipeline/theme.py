"""Thème JSON et contraste WCAG, calculés localement."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.errors import ErreurMetier
from backend.app.pipeline.schema_check import URI_THEME, erreurs

MANIFEST = json.loads(
    (Path(__file__).resolve().parents[2] / "templates" / "pbip" / "manifest.json").read_text(encoding="utf-8")
)


def _canal(valeur: str) -> tuple[int, int, int]:
    texte = valeur.strip().lstrip("#")
    if len(texte) == 3:
        texte = "".join(ch * 2 for ch in texte)
    if len(texte) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in texte):
        raise ErreurMetier("generation_echouee", "Une couleur doit être un code hexadécimal à 6 chiffres.")
    return int(texte[0:2], 16), int(texte[2:4], 16), int(texte[4:6], 16)


def normaliser_couleur(valeur: str) -> str:
    rouge, vert, bleu = _canal(valeur)
    return f"#{rouge:02X}{vert:02X}{bleu:02X}"


def _lin(canal: float) -> float:
    c = canal / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(couleur: str) -> float:
    rouge, vert, bleu = _canal(couleur)
    return 0.2126 * _lin(rouge) + 0.7152 * _lin(vert) + 0.0722 * _lin(bleu)


def ratio_contraste(a: str, b: str) -> float:
    clair, sombre = sorted((luminance(a), luminance(b)), reverse=True)
    return (clair + 0.05) / (sombre + 0.05)


def _melanger(couleur: str, cible: tuple[int, int, int], part: float) -> str:
    rouge, vert, bleu = _canal(couleur)
    return "#{:02X}{:02X}{:02X}".format(
        round(rouge + (cible[0] - rouge) * part),
        round(vert + (cible[1] - vert) * part),
        round(bleu + (cible[2] - bleu) * part),
    )


def proposer_contraste(couleur: str, fond: str, seuil: float = 3) -> str | None:
    if ratio_contraste(couleur, fond) >= seuil:
        return None
    cible = (0, 0, 0) if luminance(fond) > 0.5 else (255, 255, 255)
    for pas in range(1, 21):
        candidate = _melanger(couleur, cible, pas / 20)
        if ratio_contraste(candidate, fond) >= seuil:
            return candidate
    return _melanger(couleur, cible, 1)


def _fond_et_texte(couleurs: list[str]) -> tuple[str, str]:
    candidats = (("#FFFFFF", "#1A1A1A"), ("#1A1A1A", "#F7F4EF"))
    meilleur = max(
        candidats,
        key=lambda paire: (
            sum(1 for couleur in couleurs if ratio_contraste(couleur, paire[0]) >= 3),
            ratio_contraste(paire[0], paire[1]),
            1 if paire[0] == "#FFFFFF" else 0,
        ),
    )
    fond, encre = meilleur
    if ratio_contraste(fond, encre) < 4.5:
        encre = "#000000" if luminance(fond) > 0.5 else "#FFFFFF"
    return fond, encre


def _styles_visuels(palette: list[str], fond: str, encre: str) -> dict:
    """Cartes posées sur un fond de page légèrement teinté : cadre arrondi, ombre douce, marges internes."""
    clair = luminance(fond) > 0.5
    toile = _melanger(fond, _canal(palette[0]), 0.05) if clair else _melanger(fond, (255, 255, 255), 0.06)
    filet = _melanger(fond, (0, 0, 0), 0.10) if clair else _melanger(fond, (255, 255, 255), 0.16)
    accent = palette[0] if ratio_contraste(palette[0], fond) >= 3 else (proposer_contraste(palette[0], fond, 3) or encre)
    sans_cadre = {
        "background": [{"show": False}],
        "border": [{"show": False}],
        "dropShadow": [{"show": False}],
    }
    return {
        "*": {
            "*": {
                "background": [{"show": True, "color": {"solid": {"color": fond}}, "transparency": 0}],
                "border": [{"show": True, "color": {"solid": {"color": filet}}, "radius": 10}],
                "dropShadow": [
                    {
                        "show": True,
                        "color": {"solid": {"color": "#000000"}},
                        "transparency": 90 if clair else 70,
                        "position": "Outer",
                        "preset": "Custom",
                        "shadowBlur": 10,
                        "shadowDistance": 2,
                        "angle": 90,
                        "shadowSpread": 0,
                    }
                ],
                "padding": [{"top": 12, "bottom": 12, "left": 14, "right": 14}],
                "title": [
                    {
                        "show": True,
                        "fontColor": {"solid": {"color": encre}},
                        "fontSize": 12,
                        "fontFamily": "Segoe UI Semibold",
                    }
                ],
            }
        },
        "page": {
            "*": {
                "background": [{"color": {"solid": {"color": toile}}, "transparency": 0}],
                "outspace": [{"color": {"solid": {"color": toile}}}],
            }
        },
        # Le nom de la mesure est déjà écrit sous le chiffre : pas de titre en double.
        "card": {
            "*": {
                "title": [{"show": False}],
                "labels": [{"color": {"solid": {"color": accent}}, "fontSize": 28}],
                "categoryLabels": [{"show": True, "fontSize": 11, "color": {"solid": {"color": encre}}}],
            }
        },
        # Le segment affiche déjà le nom du champ dans son en-tête.
        "slicer": {"*": {"title": [{"show": False}]}},
        # Les titres de page sont posés directement sur le fond.
        "textbox": {"*": sans_cadre},
    }


def construire_theme(couleurs: list[str]) -> dict:
    if not 3 <= len(couleurs) <= 5:
        raise ErreurMetier("generation_echouee", "Le thème demande entre 3 et 5 couleurs.")
    palette = [normaliser_couleur(couleur) for couleur in couleurs]
    fond, encre = _fond_et_texte(palette)
    premiere, deuxieme, troisieme = palette[0], palette[1], palette[min(2, len(palette) - 1)]
    minimum = _melanger(premiere, (255, 255, 255), 0.82)
    theme = {
        "name": "Rapport",
        "dataColors": palette,
        "background": fond,
        "foreground": encre,
        "tableAccent": premiere,
        "good": premiere,
        "neutral": deuxieme,
        "bad": troisieme,
        "maximum": premiere,
        "center": deuxieme,
        "minimum": minimum,
        "null": "#8A8A8A",
        "textClasses": {
            "callout": {"fontFace": "Segoe UI", "fontSize": 28, "color": encre},
            "title": {"fontFace": "Segoe UI", "fontSize": 12, "color": encre},
            "header": {"fontFace": "Segoe UI Semibold", "fontSize": 14, "color": encre},
            "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": encre},
        },
        "visualStyles": _styles_visuels(palette, fond, encre),
    }
    problemes = erreurs(theme, URI_THEME)
    if problemes:
        raise ErreurMetier(
            "generation_echouee",
            "La génération s'est arrêtée. Le thème ne respecte pas le schéma vendored.",
        )
    contrastes = []
    for couleur in palette:
        mesure = ratio_contraste(couleur, fond)
        contrastes.append(
            {
                "couleur": couleur,
                "ratio": round(mesure, 2),
                "seuil": 3,
                "suffisant": mesure >= 3,
                "proposition": proposer_contraste(couleur, fond, 3),
            }
        )
    return {
        "theme": theme,
        "contrastes": contrastes,
        "contraste_texte": {
            "foreground": encre,
            "background": fond,
            "ratio": round(ratio_contraste(fond, encre), 2),
        },
    }
