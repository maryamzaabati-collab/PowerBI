"""Validation JSON hors ligne, schémas vendored uniquement."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

RACINE = Path(__file__).resolve().parents[2]
VENDOR = RACINE / "schemas" / "vendor"
THEME = RACINE / "schemas" / "theme" / "reportThemeSchema-2.157.json"
URI_THEME = "https://local.schemas/powerbi/reportThemeSchema-2.157.json"


@lru_cache(maxsize=1)
def registre() -> Registry:
    registre_local: Registry = Registry()
    for chemin in VENDOR.rglob("*.json"):
        contenu = json.loads(chemin.read_text(encoding="utf-8"))
        ressource = Resource.from_contents(contenu, default_specification=DRAFT7)
        url = "https://" + chemin.relative_to(VENDOR).as_posix()
        registre_local = registre_local.with_resource(url, ressource)
        identifiant = contenu.get("$id")
        if isinstance(identifiant, str) and identifiant != url:
            registre_local = registre_local.with_resource(identifiant, ressource)
    theme = json.loads(THEME.read_text(encoding="utf-8"))
    registre_local = registre_local.with_resource(
        URI_THEME, Resource.from_contents(theme, default_specification=DRAFT7)
    )
    return registre_local


def erreurs(instance: object, schema_url: str) -> list[str]:
    """Liste vide si l'instance respecte le schéma. Aucun accès réseau."""
    schema = registre().get_or_retrieve(schema_url).value.contents
    validateur = Draft7Validator(schema, registry=registre())
    trouvailles = sorted(validateur.iter_errors(instance), key=lambda e: list(e.path))
    messages: list[str] = []
    for erreur in trouvailles:
        chemin = "/".join(str(p) for p in erreur.path) or "(racine)"
        messages.append(f"{chemin}: {erreur.message}")
    return messages


def exige(instance: object, schema_url: str) -> None:
    trouvailles = erreurs(instance, schema_url)
    if trouvailles:
        apercu = "; ".join(trouvailles[:6])
        raise ValidationError(apercu)
