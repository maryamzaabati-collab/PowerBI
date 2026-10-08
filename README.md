# Pack Power BI

Outil local : on dépose un CSV, on choisit 3 à 5 couleurs, on télécharge un ZIP. Le ZIP contient un projet PBIP (modèle TMDL, rapport PBIR), un script Power Query, les mesures DAX, un thème JSON, le CSV nettoyé, le journal et un compte rendu Word.

Le programme ne pilote pas Power BI Desktop. Il n'envoie pas les lignes à un autre service : pas de géocodage, pas de CDN, pas de modèle de langage. Sur Replit, le CSV est traité **sur la machine Replit**, par l'API de ce dépôt. Il n'est pas transmis à un service d'analyse tiers.

Les visuels PBIR sont validés contre des schémas JSON publics copiés dans `backend/schemas`. Un fichier accepté par ces schémas peut encore être refusé par Desktop. Ce dépôt n'a pas été ouvert dans Power BI Desktop : le logiciel n'était pas disponible. Le gabarit est écrit à la main. Voir `backend/templates/VERSION.txt`.

## Installation locale (deux processus)

Python 3.11 et Node 20.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8741
```

Dans un second terminal :

```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 8742
```

Ouvrir http://127.0.0.1:8742. L'interface appelle l'API sur le port 8741.

Limites : 50 Mo, 200 000 lignes, 80 colonnes. Session de 2 heures. Les fichiers temporaires sont dans `PBI_PACK_TMP` ou dans le dossier temporaire du système (`pbi-pack/`), vidés au démarrage de l'API.

## Importer ce dépôt dans Replit, puis Run, puis Publish

1. Dans Replit : Create Repl → Import from GitHub, avec l'URL de ce dépôt.
2. Lancer avec le bouton **Run**. Le script `start.sh` installe les dépendances s'il le faut, construit le frontend, puis démarre uvicorn.
3. Si la variable `PORT` est définie (cas de Replit), l'API écoute `0.0.0.0:$PORT` et sert le frontend déjà construit. Un seul port public.
4. **Publish** publie cette même application. Le CSV déposé dans le navigateur est lu et transformé par le conteneur Replit. Il ne part pas vers un autre outil d'analyse.

En local, sans `PORT`, le développement reste en deux processus (uvicorn et Vite), comme ci-dessus. `start.sh` sans `PORT` ne lance que l'API sur `127.0.0.1:8741`, après avoir construit le frontend.

## Ouvrir le ZIP

1. Ouvrir `Rapport.pbip` avec Power BI Desktop grand public (pas l'édition Report Server).
2. Transformer les données → Modifier les paramètres → `CheminFichierCsv` = chemin absolu de `donnees/donnees-nettoyees.csv`.
3. Actualiser.
4. Si les couleurs n'ont pas suivi : Affichage → Thèmes → Parcourir les thèmes → `theme/theme.json`.
5. Si le niveau annoncé est B ou C : poser les visuels listés dans `LISEZMOI.txt`. Les mesures sont dans le modèle.
6. Confirmer le marquage « table de dates » sur `Calendrier[Date]` si Desktop le demande.
7. Pour retraiter un fichier brut : coller `power-query/nettoyage.pq` dans une requête vide et viser `donnees/source.csv`.
8. Dans Word, mettre à jour les champs du sommaire si l'application le propose.

## Automatique et à finir à la main

Automatique dans le ZIP : profil, nettoyage pandas, journal, CSV nettoyé, `nettoyage.pq` commenté, modèle TMDL (faits, calendrier, dimension seulement si un préfixe groupe des colonnes dont l'identifiant se répète), `mesures.dax`, `theme.json` validé, cinq pages PBIR, compte rendu.

À la main dans Desktop : chemin du CSV et actualisation, thème si les couleurs ne suivent pas, visuels aux niveaux B et C, confirmation de la table de dates, mise à jour du sommaire Word, relecture d'une date ambiguë signalée dans le journal.

Les dates ambiguës du type `01/02/2024` sont lues en jour/mois/année et écrites en `AAAA-MM-JJ`.
