# job-bot-general

Projet Python conteneurisé avec trois services Docker Compose :

- `analyzer` : traitement batch d'analyse et production de `output/job_data.json`
- `generator` : traitement batch de génération à partir des données analysées
- `dashboard` : interface Streamlit pour suivre l'état du projet, la configuration et consulter les résultats

## Démarrage rapide

1. Copier `.env.example` vers `.env`
2. Renseigner les clés API nécessaires
3. Placer votre CV Europass dans `data/resume_europass.txt`
4. Lancer l'ensemble :

```bash
docker compose up --build
```

5. Ouvrir le dashboard : http://localhost:8501

## Workflow recommandé

- `analyzer` et `generator` sont des services batch : ils exécutent leur traitement puis s'arrêtent normalement.
- `dashboard` reste disponible pour visualiser :
  - l'état des fichiers d'entrée/sortie
  - la progression globale du pipeline
  - les logs Docker des services
  - la disponibilité de la configuration OpenAI / Anthropic

Si vous modifiez les données d'entrée et souhaitez relancer le pipeline :

```bash
docker compose up --build analyzer generator
```

Le dashboard peut rester lancé en parallèle.

## Volumes et fichiers utilisés

- `./data:/data` : fichiers d'entrée, notamment le CV
- `./output:/output` : fichiers générés par l'analyse et la génération

Fichiers principaux attendus :

- `data/resume_europass.txt`
- `output/job_data.json`
- `output/generation_results.json`

## Architecture MCP (OpenAI + Anthropic)

Un serveur MCP dédié est disponible dans `mcp_server/`.

Il expose déjà les outils suivants :

- `europass_pdf_to_json` : conversion d'un CV Europass PDF vers JSON structuré
- `job_url_to_json` : conversion d'une URL d'offre en JSON structuré
- `career_strategy_openai` : stratégie carrière via OpenAI
- `career_strategy_anthropic` : stratégie carrière via Anthropic
- `career_strategy_dual` : exécution OpenAI + Anthropic
- `career_pipeline_from_pdf_and_url` : pipeline complet PDF CV + URL offre -> pack final JSON

Les modèles sont détectés dynamiquement via API (pas de hardcode modèle), avec adaptation automatique de `max_tokens` côté Anthropic.

Lancement du serveur MCP :

```bash
docker compose --profile mcp up --build mcp
```

Ou en local :

```bash
cd mcp_server
pip install -r requirements.txt
python main.py
```

## Remarque sur les logs dans le dashboard

Le service `dashboard` monte le socket Docker en lecture seule (`/var/run/docker.sock`) afin de pouvoir consulter les logs des conteneurs et mieux afficher l'état d'exécution dans l'interface. Si votre environnement ne permet pas ce montage, le dashboard doit continuer à fonctionner, mais avec une visibilité réduite sur les logs temps réel.

## GitHub Actions incluses

- `.github/workflows/docker-build.yml` construit les images Docker sur `push` et `pull request`
- `.github/workflows/docker-publish-ghcr.yml` publie les images sur GHCR lors des pushes sur `main`

## Paramètres GitHub recommandés pour la publication

- Dépôt public recommandé pour simplifier les pulls GHCR
- Permissions Actions :
  - Contents: Read
  - Packages: Write

## Secrets optionnels

Pour un déploiement réel au-delà de la publication d'images, ajoutez votre propre cible de déploiement et les secrets nécessaires.