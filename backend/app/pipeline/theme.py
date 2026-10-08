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
        "visualStyles": {
            "*": {
                "*": {
                    "background": [{"color": {"solid": {"color": fond}}}]
                }
            }
        },
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
