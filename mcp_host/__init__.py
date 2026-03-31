"""
mcp_host — Architecture MCP Professionnelle Top-Down
=====================================================

Structure :
  mcp_host/
    main.py              # Orchestrateur/Host + Factory + boucle LLM
    core/
      base_client.py     # BaseMCPClient abstraite (SDK officiel mcp.ClientSession)
    clients/
      postgres_client.py # npx @modelcontextprotocol/server-postgres
      fetch_client.py    # uvx mcp-server-fetch
      filesystem_client.py # npx @modelcontextprotocol/server-filesystem
      github_client.py   # npx @modelcontextprotocol/server-github
      scrapegraph_client.py # uvx scrapegraph-mcp@1.0.1
    servers/
      registry.py        # Registre centralisé + validation npx/uv
    utils/
      translator.py      # Convertisseur MCP → OpenAI/Anthropic JSON Schema
    Dockerfile           # Hybrid: python:3.11-slim + Node.js 20 + npx + uv
"""
