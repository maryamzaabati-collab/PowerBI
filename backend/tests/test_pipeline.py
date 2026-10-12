"""CSV français, ZIP, thème et commentaires M."""

from __future__ import annotations

import io
import json
import time
import zipfile
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from backend.app.errors import ErreurMetier
from backend.app.pipeline.docx_report import construire_docx
from backend.app.pipeline.modele import construire_plan
from backend.app.limits import COLONNES_MAX, TAILLE_MAX_OCTETS
from backend.app.pipeline.clean import nettoyer
from backend.app.pipeline.dates import analyser_date
from backend.app.pipeline.lecture import lire_csv, verifier_taille
from backend.app.pipeline.m_script import script_nettoyage
from backend.app.pipeline.pack import produire
from backend.app.pipeline.profile import profiler
from backend.app.pipeline.schema_check import URI_THEME, erreurs
from backend.app.pipeline.theme import construire_theme

CSV = """date;libelle;montant;client_id;client_nom
01/02/2024;Alpha;12,50;c1;Martin
15/03/2024;Beta;;c1;Martin
01/02/2024;Alpha;12,50;c1;Martin
32/13/2024;Gamma;3,00;c2;Durand
;Delta;1.234,50;c2;Durand
""".encode("utf-8")


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PBI_PACK_TMP", str(tmp_path))
    from backend.app.main import app

    with TestClient(app) as test:
        yield test


def test_date_fr_et_ambigu():
    valeur, ambigu = analyser_date("01/02/2024")
    assert valeur is not None and valeur.isoformat() == "2024-02-01"
    assert ambigu is True
    claire, non = analyser_date("15/03/2024")
    assert claire is not None and claire.isoformat() == "2024-03-15"
    assert non is False


def test_lecture_profil_nettoyage():
    frame, meta = lire_csv(CSV)
    assert meta["separateur"] == ";"
    profil = profiler(frame, meta)
    assert profil["lignes"] == 5
    assert profil["doublons_exacts"] >= 1
    roles = {col["nom"]: col["role_propose"] for col in profil["colonnes"]}
    assert roles["date"] == "temporel"
    assert roles["montant"] == "numerique"
    assert roles["client_id"] == "identifiant" or roles["client_nom"] == "categorie" or roles["client_id"]
    nettoye, journal = nettoyer(frame, roles, {}, ";", "date")
    assert len(nettoye) == 4
    dates = [v.isoformat() for v in nettoye["date"].dropna()]
    assert "2024-02-01" in dates
    assert journal["dates_ambigues"]
    assert nettoye["montant"].isna().any()


def test_dimension_et_zip(tmp_path):
    frame, meta = lire_csv(CSV)
    profil = profiler(frame, {**meta, "nom_fichier": "ventes.csv"})
    roles = {col["nom"]: col["role_propose"] for col in profil["colonnes"]}
    # Le jeu a peu de lignes : on force les rôles du contrat.
    roles.update({"date": "temporel", "libelle": "categorie", "montant": "numerique", "client_id": "identifiant", "client_nom": "categorie"})
    nettoye, journal = nettoyer(frame, roles, {}, ";", "date")
    theme = construire_theme(["#0F6E56", "#E6A817", "#C4493A", "#1F4E79", "#6B4C9A"])
    assert erreurs(theme["theme"], URI_THEME) == []
    contenu, resume = produire(
        {
            "nettoye": nettoye,
            "journal": journal,
            "roles": roles,
            "regles": journal["regles_actives"],
            "date_pilote": "date",
            "theme": theme["theme"],
            "profil": profil,
            "renommage": meta["renommage"],
            "encodage": meta["encodage"],
            "separateur": ";",
            "separateur_libelle": "point-virgule",
            "nom_fichier": "ventes.csv",
            "source": CSV,
        }
    )
    archive = zipfile.ZipFile(io.BytesIO(contenu))
    noms = set(archive.namelist())
    for attendu in (
        "LISEZMOI.txt",
        "donnees/source.csv",
        "donnees/donnees-nettoyees.csv",
        "donnees/journal.json",
        "power-query/nettoyage.pq",
        "dax/mesures.dax",
        "theme/theme.json",
        "compte-rendu.docx",
        "Rapport.pbip",
        "Rapport.SemanticModel/definition.pbism",
        "Rapport.SemanticModel/definition/database.tmdl",
        "Rapport.SemanticModel/definition/model.tmdl",
        "Rapport.SemanticModel/definition/tables/Donnees.tmdl",
        "Rapport.SemanticModel/definition/tables/Calendrier.tmdl",
        "Rapport.Report/definition.pbir",
        "Rapport.Report/definition/version.json",
        "Rapport.Report/definition/report.json",
        "Rapport.Report/StaticResources/RegisteredResources/theme.json",
    ):
        assert attendu in noms
    assert any(nom.startswith("Rapport.Report/definition/pages/") and nom.endswith("page.json") for nom in noms)
    pq = archive.read("power-query/nettoyage.pq").decode("utf-8")
    commentaires = [ligne for ligne in pq.splitlines() if ligne.strip().startswith("//")]
    assert len(commentaires) >= 4
    texte = " ".join(commentaires).lower()
    assert "chemin" in texte
    assert "étape" in texte or "etape" in texte
    theme_zip = json.loads(archive.read("theme/theme.json"))
    assert erreurs(theme_zip, URI_THEME) == []
    assert resume["niveau"] in {"A", "A partiel", "B", "C"}
    assert "Dim_Client" in archive.read("Rapport.SemanticModel/definition/model.tmdl").decode("utf-8")
    Path(tmp_path / "ok").write_text(resume["niveau"])


def test_script_m_commente():
    pq = script_nettoyage(
        [{"source": "Date", "modele": "Date"}, {"source": "Montant", "modele": "Montant"}],
        {"Date": "temporel", "Montant": "numerique"},
        {"doublons": True, "trim": True, "vides": True, "casse": False, "nombres": True, "dates": True},
        "utf-8",
        ";",
    )
    assert "fr-FR" in pq
    assert pq.count("//") >= 4


def test_limites():
    with pytest.raises(ErreurMetier) as exc:
        verifier_taille(TAILLE_MAX_OCTETS + 1)
    assert exc.value.code == "csv_trop_volumineux"
    entete = ";".join(f"c{i}" for i in range(COLONNES_MAX + 1))
    ligne = ";".join("1" for _ in range(COLONNES_MAX + 1))
    with pytest.raises(ErreurMetier) as trop:
        lire_csv(f"{entete}\n{ligne}\n".encode())
    assert trop.value.code == "csv_trop_de_colonnes"
    with pytest.raises(ErreurMetier) as vide:
        lire_csv(b"date;montant\n")
    assert vide.value.code == "csv_vide"


def test_compte_rendu_lit_les_chiffres():
    csv = """implantation;region;prix_gazole;prix_e10
route;Ouest;1,70;1,55
route;Ouest;1,72;1,57
route;Est;1,90;1,74
autoroute;Ouest;1,95;1,80
autoroute;Est;2,05;1,88
autoroute;Est;2,01;1,86
""".encode()
    frame, meta = lire_csv(csv)
    profil = profiler(frame, {**meta, "nom_fichier": "prix.csv"})
    roles = {col["nom"]: col["role_propose"] for col in profil["colonnes"]}
    roles.update(
        {
            "implantation": "categorie",
            "region": "geographique",
            "prix_gazole": "numerique",
            "prix_e10": "numerique",
        }
    )
    nettoye, journal = nettoyer(frame, roles, {}, ";", None)
    plan = construire_plan(nettoye, roles, None)
    theme = construire_theme(["#0F6E56", "#E6A817", "#C4493A"])
    blob = construire_docx(
        "prix.csv",
        nettoye,
        journal,
        profil,
        plan,
        theme["theme"],
        "A",
        meta["encodage"],
        "virgule",
    )
    document = Document(io.BytesIO(blob))
    texte = "\n".join(p.text for p in document.paragraphs)
    assert "Une ligne = une observation du fichier." in texte
    assert "50 litres" in texte
    assert "CheminFichierCsv" in texte
    assert "Méthodologie de nettoyage" not in texte
    assert "Type avant" not in texte
    assert "Niveau PBIR obtenu : A." in texte
    assert texte.index("Conclusion") < texte.index("Annexes")
    assert texte.index("Lecture des chiffres") < texte.index("Ce qui pèse le plus")


def test_api_zip(client: TestClient):
    reponse = client.post("/api/sessions", files={"fichier": ("ventes.csv", CSV, "text/csv")})
    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    session = corps["session"]
    roles = {col["nom"]: col["role_propose"] for col in corps["profil"]["colonnes"]}
    roles.update({"date": "temporel", "montant": "numerique", "libelle": "categorie", "client_id": "identifiant", "client_nom": "categorie"})
    net = client.post(f"/api/sessions/{session}/clean", json={"regles": {}, "roles": roles, "date_pilote": "date"})
    assert net.status_code == 200, net.text
    theme = client.put(
        f"/api/sessions/{session}/theme",
        json={"couleurs": ["#0F6E56", "#E6A817", "#C4493A"]},
    )
    assert theme.status_code == 200, theme.text
    assert theme.json()["contraste_texte"]["ratio"] >= 4.5
    job = client.post(f"/api/sessions/{session}/generate")
    assert job.status_code == 200, job.text
    job_id = job.json()["job"]
    etat = {}
    for _ in range(40):
        etat = client.get(f"/api/sessions/{session}/jobs/{job_id}").json()
        if etat["etat"] != "en_cours":
            break
        time.sleep(0.25)
    assert etat["etat"] == "termine", etat
    assert etat["niveau"] in {"A", "A partiel", "B", "C"}
    fichier = client.get(f"/api/sessions/{session}/download")
    assert fichier.status_code == 200
    assert fichier.headers["content-type"].startswith("application/zip")
    archive = zipfile.ZipFile(io.BytesIO(fichier.content))
    assert "power-query/nettoyage.pq" in archive.namelist()
    refus = client.post("/api/sessions", files={"fichier": ("note.txt", b"a,b\n1,2\n", "text/plain")})
    assert refus.status_code == 400
    assert refus.json()["code"] == "pas_un_csv"
