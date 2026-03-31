# TODO — Refonte Architecture MCP Professionnelle (Top-Down & Docker)

## Statut global : ✅ Complété

---

## Étapes

- [x] 1. Créer `mcp_host/core/__init__.py`
- [x] 2. Créer `mcp_host/core/base_client.py` — BaseMCPClient abstraite (SDK officiel)
- [x] 3. Créer `mcp_host/servers/__init__.py`
- [x] 4. Créer `mcp_host/servers/registry.py` — Registre centralisé + validation npx/uv
- [x] 5. Créer `mcp_host/clients/__init__.py`
- [x] 6. Créer `mcp_host/clients/postgres_client.py`
- [x] 7. Créer `mcp_host/clients/fetch_client.py`
- [x] 8. Créer `mcp_host/clients/filesystem_client.py`
- [x] 9. Créer `mcp_host/clients/github_client.py`
- [x] 10. Créer `mcp_host/clients/scrapegraph_client.py`
- [x] 11. Créer `mcp_host/utils/__init__.py`
- [x] 12. Créer `mcp_host/utils/translator.py` — Convertisseur MCP → OpenAI/Anthropic JSON Schema
- [x] 13. Créer `mcp_host/main.py` — Orchestrateur/Host + Factory
- [x] 14. Créer `mcp_host/Dockerfile` — Hybrid Python 3.11 + Node.js 20 + npx + uv
- [x] 15. Modifier `docker-compose.yml` — Service `mcp-host` + réseau `mcp-net` + healthcheck postgres
- [x] 16. Modifier `.vscode/mcp.json` — 6 serveurs MCP (ScrapeGraph, Host, Fetch, Filesystem, GitHub, Postgres)
- [x] 17. Supprimer `mcp_server/` source files (reste __pycache__ root-owned → `sudo rm -rf mcp_server/`)

---

## Arborescence finale

```
mcp_host/
  __init__.py
  main.py              # Orchestrateur/Host + Factory + boucle OpenAI/Anthropic
  Dockerfile           # Hybrid: python:3.11-slim + Node.js 20 + npx + uv
  core/
    __init__.py
    base_client.py     # BaseMCPClient abstraite (mcp.ClientSession + reconnexion auto)
  clients/
    __init__.py
    postgres_client.py   # npx @modelcontextprotocol/server-postgres
    fetch_client.py      # uvx mcp-server-fetch
    filesystem_client.py # npx @modelcontextprotocol/server-filesystem
    github_client.py     # npx @modelcontextprotocol/server-github
    scrapegraph_client.py # uvx scrapegraph-mcp@1.0.1
  servers/
    __init__.py
    registry.py        # Registre centralisé + validation npx/uv au démarrage
  utils/
    __init__.py
    translator.py      # Convertisseur MCP → OpenAI/Anthropic JSON Schema
```

---

## Notes post-implémentation

- `mcp_server/__pycache__/` (root-owned) : supprimer avec `sudo rm -rf mcp_server/`
- Variables d'env requises dans `.env` : `OPENAI_API_KEY`, `SGAI_API_KEY`, `GH_TOKEN`, `DATABASE_URL`
- Lancer le host MCP : `docker compose --profile mcp up mcp-host`
- Test local : `python -m mcp_host.main --list-registry`
- Test outils : `python -m mcp_host.main --list-tools`
