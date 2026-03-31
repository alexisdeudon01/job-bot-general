# MCP transport recommendations for OpenAI-first orchestration

## Summary recommendation

Use a **transport-by-deployment-context** approach:

- **Local ScrapeGraph MCP:** use **stdio** as the default and primary transport.
- **Remote/self-hosted internal MCP services:** support **streamable HTTP** as the preferred network transport.
- **Legacy or third-party hosted MCPs that only expose SSE:** support **SSE** as a compatibility transport, not as the default for new internal services.

This matches the current repository shape:

- `mcp_server/main.py` already runs the local MCP with `transport="stdio"`.
- `app/services/orchestration_service.py` currently assumes an in-process/local `ScrapeGraphStdioClient`.
- `.vscode/mcp.json` already documents a stdio MCP server pattern.
- `mcp_server/services/scrapegraph_service.py` is built around local credentials and local process execution, which is a good fit for stdio.

## Why stdio is the right default for local ScrapeGraph

For this project, the local ScrapeGraph MCP is best represented as a subprocess launched by the OpenAI Agents SDK through an MCP stdio server definition.

### Strengths

- **Best fit for local development**
  - No separate port management is required.
  - No extra HTTP server lifecycle is needed.
  - Works naturally with local env var injection such as `SGAI_API_KEY`.

- **Safer local trust boundary**
  - ScrapeGraph access stays within a local child process.
  - Fewer accidental network exposure risks than binding a local MCP HTTP server.

- **Aligned with current repo**
  - `mcp_server/main.py` is already configured for stdio.
  - `ScrapeGraphService.build_server_command_string()` already generates a subprocess command.
  - Existing orchestration concepts already think in terms of “start local MCP command then call tools”.

- **Good tool semantics**
  - Scrape/extract/markdownify are request/response tool calls, which fit stdio well.
  - There is no current need for browser-based client access to the local MCP server.

### Tradeoffs

- Harder to share one local MCP instance across many independent services.
- Less convenient for remote deployment or cross-host access.
- Process lifecycle must be managed by the caller, which is acceptable for the OpenAI Agents SDK local MCP pattern.

## Why streamable HTTP should be the preferred remote option

For future MCP servers that may be hosted remotely or shared across services, prefer **streamable HTTP** over SSE for new internal implementations.

### Strengths

- **Better long-term network transport**
  - Cleaner fit for hosted services, containers, and service-to-service deployment.
  - Easier to place behind ingress, auth layers, and observability tooling.
  - Better default for multi-client and horizontally scaled access patterns.

- **More flexible deployment topology**
  - Can be hosted as a shared MCP endpoint for app, dashboard, workers, or external tools.
  - Easier than stdio when the MCP server runs in Docker/Kubernetes or on another machine.

- **Good future-proofing**
  - If the project later adds remote MCPs for search, document retrieval, ATS integrations, or internal knowledge systems, streamable HTTP is the cleanest default representation.

### Tradeoffs

- More moving parts than stdio for purely local use.
- Requires explicit URL configuration and likely auth headers.
- Slightly more infrastructure work than launching a subprocess.

## Where SSE fits

Use **SSE** only when needed for compatibility with external/legacy MCP servers.

### Recommended use cases

- Third-party MCP providers that already expose SSE endpoints.
- Transitional support where a server does not yet offer streamable HTTP.
- Experiments or vendor integrations where the transport is fixed externally.

### Why not make SSE the project default

- It is less attractive than stdio for local process-based servers.
- It is less attractive than streamable HTTP for new hosted internal services.
- It should be treated as a supported transport mode, not the canonical one.

## Recommended project transport policy

### 1. Local MCP servers
Represent local MCP servers as **stdio subprocess servers**.

Primary example:
- Local ScrapeGraph MCP launched from repository code.

### 2. Remote MCP servers
Represent remote MCP servers as **HTTP-addressed servers**, with:
- **`streamable_http`** preferred
- **`sse`** supported as fallback/compatibility

### 3. Project code should not hard-code ScrapeGraph as “stdio-only”
Even though ScrapeGraph is currently local and should use stdio by default, the orchestration layer should evolve toward a generic MCP server configuration model that can represent:
- `stdio`
- `sse`
- `streamable_http`

## Integration contract for project code

The parent agent should move the codebase toward a transport-agnostic MCP configuration contract.

### Recommended config shape

Represent every MCP server with a typed config object like:

```python
{
    "name": "scrapegraph",
    "transport": "stdio" | "sse" | "streamable_http",
    "enabled": True,
    "cache_tools_list": True,
    "stdio": {
        "command": "python",
        "args": ["-m", "mcp_server.main"],
        "env": {
            "SGAI_API_KEY": "...",
        },
    },
    "sse": {
        "url": "https://example.com/mcp/sse",
        "headers": {
            "Authorization": "Bearer ...",
        },
    },
    "streamable_http": {
        "url": "https://example.com/mcp",
        "headers": {
            "Authorization": "Bearer ...",
        },
    },
}
```

Only the sub-object matching `transport` should be required at runtime.

### Recommended Python dataclass contract

This repo already uses dataclasses in service layers, so a natural integration contract is:

- `MCPServerTransport = Literal["stdio", "sse", "streamable_http"]`
- `MCPStdioConfig`
- `MCPSseConfig`
- `MCPStreamableHttpConfig`
- `MCPServerConfig`

Suggested field responsibilities:

#### `MCPStdioConfig`
- `command: str`
- `args: list[str]`
- `env: dict[str, str] | None = None`
- optional `cwd: str | None = None`

#### `MCPSseConfig`
- `url: str`
- `headers: dict[str, str] | None = None`
- optional timeout/retry fields if the parent agent wants them later

#### `MCPStreamableHttpConfig`
- `url: str`
- `headers: dict[str, str] | None = None`
- optional timeout/retry fields if needed

#### `MCPServerConfig`
- `name: str`
- `transport: MCPServerTransport`
- `enabled: bool = True`
- `stdio: MCPStdioConfig | None = None`
- `sse: MCPSseConfig | None = None`
- `streamable_http: MCPStreamableHttpConfig | None = None`

Validation contract:
- exactly one transport-specific config should be populated for the declared transport
- `name` should be stable and used for logs/telemetry
- callers should not inspect transport internals outside the MCP adapter/factory layer

## ScrapeGraph-specific contract

### Default representation
ScrapeGraph should be represented in project code as:

- `name = "scrapegraph"`
- `transport = "stdio"`

### Command contract
Use the existing server entrypoint pattern already present in the repo:

- command: `python`
- args: `["-m", "mcp_server.main"]`

This is consistent with:
- `mcp_server/main.py`
- `ScrapeGraphService.build_server_command()`
- `ScrapeGraphService.build_server_command_string()`

### Environment contract
The stdio server config should pass through:
- `SGAI_API_KEY`

If the parent agent centralizes config in `app/core/config.py`, the local MCP config should be derivable there without embedding secrets in code.

### Tool contract
The orchestration layer should continue to treat ScrapeGraph as a named MCP tool provider exposing tools such as:
- `scrapegraph_markdownify`
- `scrapegraph_extract`
- `scrapegraph_search_extract`

The new OpenAI Agents SDK integration should map the MCP server itself, not reimplement these tools as OpenAI-native tools.

## Factory/adapter contract for the parent agent

The codebase should add a single MCP adapter/factory layer responsible for converting `MCPServerConfig` into the OpenAI Agents SDK server object.

Recommended behavior:

- if `transport == "stdio"`:
  - build an OpenAI Agents SDK `MCPServerStdio`
- if `transport == "sse"`:
  - build an OpenAI Agents SDK `MCPServerSse`
- if `transport == "streamable_http"`:
  - build an OpenAI Agents SDK `MCPServerStreamableHttp`

This keeps:
- orchestration logic transport-agnostic
- OpenAI SDK specifics isolated in one service/module
- future MCP additions easy to register

## Recommended file-level representation changes for the parent agent

These are recommendations only; this sub-task does not modify application code.

### `app/services/orchestration_service.py`
Current issue:
- It directly depends on `ScrapeGraphStdioClient`, which couples orchestration to one transport and one provider implementation detail.

Recommendation:
- Replace direct `ScrapeGraphStdioClient` dependency with a generic MCP server registry or MCP service abstraction.
- The orchestration planner may still recommend `provider="scrapegraph"`, but execution should route through an OpenAI MCP-backed adapter rather than a bespoke stdio-only client.

### `mcp_server/clients/scrapegraph_stdio_client.py`
Current role:
- local adapter for direct tool calls.

Recommendation:
- Keep only as temporary compatibility code if needed.
- Long term, replace with a transport-neutral MCP configuration + OpenAI Agents SDK MCP server factory.
- Do not build new features on this class.

### `mcp_server/main.py`
Current status:
- Correct for local stdio use.

Recommendation:
- Keep stdio entrypoint behavior for local use.
- If remote hosting is needed later, add a separate hosted entrypoint or configurable transport bootstrap rather than changing the local default.

## Recommended future MCP inventory model

The project is likely to benefit from at least three server categories:

### Local/private subprocess MCPs
Use `stdio`:
- ScrapeGraph local MCP
- local filesystem or repo-analysis MCPs
- development-only experimental tools

### Internal hosted MCPs
Use `streamable_http`:
- ATS integration MCP
- internal document retrieval MCP
- entity enrichment or knowledge graph MCP
- shared organization services

### External vendor MCPs
Use `sse` or `streamable_http` depending on vendor support:
- prefer `streamable_http` when offered
- support `sse` when that is the vendor’s only MCP transport

## Concrete recommendation to the parent agent

1. **Keep ScrapeGraph on stdio**
   - This is the best immediate fit for the local repo and OpenAI Agents SDK MCP support.

2. **Introduce a transport-neutral MCP config model**
   - Required so the codebase does not remain locked to `ScrapeGraphStdioClient`.

3. **Prefer streamable HTTP for all new remote/internal MCP services**
   - Use SSE only when compatibility requires it.

4. **Treat SSE as supported, not preferred**
   - Good fallback, not the default architecture choice.

5. **Make orchestration select servers by logical name, not transport class**
   - Example: `"scrapegraph"` instead of `"stdio client"`.

## Short decision matrix

| Scenario | Recommended transport | Reason |
|---|---|---|
| Local ScrapeGraph MCP in this repo | `stdio` | simplest local process integration, already matches repo |
| New remote internal MCP service | `streamable_http` | best hosted/service deployment shape |
| External MCP vendor with SSE-only offering | `sse` | compatibility mode |
| Shared cross-container MCP used by many services | `streamable_http` | easier ops, auth, routing, scaling |
| Dev-only experimental local tool server | `stdio` | low setup overhead |

## Parent-agent handoff notes

This document defines the recommended contract other code should follow:

- stable transport enum values:
  - `stdio`
  - `sse`
  - `streamable_http`

- stable logical server name for local ScrapeGraph:
  - `scrapegraph`

- stable local command pattern for ScrapeGraph:
  - `python -m mcp_server.main`

- architecture rule:
  - **orchestration code depends on logical MCP server configs, not concrete transport-specific client classes**