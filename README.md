# job-bot-general

Project package prepared for GitHub with Docker and GitHub Actions.

## Quick start

1. Copy `.env.example` to `.env`
2. Fill in your API keys
3. Put your Europass CV in `data/resume_europass.txt`
4. Run:

```bash
docker compose up --build
```

## GitHub Actions included

- `.github/workflows/docker-build.yml` builds all Docker images on push and pull request
- `.github/workflows/docker-publish-ghcr.yml` publishes images to GHCR on pushes to `main`

## Required GitHub repo settings for publish

- Public repo recommended for easiest GHCR pulls
- Actions permissions:
  - Contents: Read
  - Packages: Write

## Optional secrets

For real deployment beyond image publish, add your own deployment target and required secrets.
