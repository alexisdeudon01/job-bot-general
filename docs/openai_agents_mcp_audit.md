# OpenAI Agents SDK MCP integration audit

## Files that must change

### `app/services/orchestration_service.py`
- Remove Anthropic-specific constructor args, attributes, provider selection, capability reporting, and fallback chain logic.
- Replace generic/dual-provider routing with OpenAI-first execution and, for MCP-backed scraping, an OpenAI Agents SDK integration path.
- Key areas:
  - `OrchestrationPlanner.__init__`
  - `OrchestrationPlanner._select_llm_provider`
  - `OrchestrationService.__init__`
  - `OrchestrationService.describe_routing_capabilities`
  - `OrchestrationService._resolve_provider_chain`
  - Any `"anthropic"` literals in planner/provider maps
- Likely new abstraction: represent OpenAI model-only operations separately from OpenAI+MCP agent runs.

### `app/services/openai_service.py`
- Keep existing plain OpenAI Responses API methods if still needed for direct text/structured extraction.
- Extend or complement this service with an OpenAI Agents SDK-based MCP runner for tool-enabled execution.
- Current note in `get_capability_descriptors()` says OpenAI service does not expose MCP tools directly; that becomes outdated and must change.
- Likely additions:
  - MCP server config dataclass(s)
  - factory/build methods for `MCPServerStdio`, `MCPServerSse`, `MCPServerStreamableHttp`
  - agent-run method for tool-backed tasks
- Likely split is cleaner than overloading current Responses-only service.

### `mcp_server/clients/scrapegraph_stdio_client.py`
- This is currently a local Python adapter that mimics stdio-callable tools, not an actual Agents SDK MCP server registration.
- It may still be useful for local/internal non-agent execution, but it is not the integration point OpenAI Agents SDK wants.
- If moving fully to Agents SDK MCP, this file becomes optional or legacy.
- At minimum, decide whether to:
  - keep it for non-agent direct execution, or
  - retire it in favor of OpenAI Agents SDK MCP server objects pointed at the local MCP server process.

### `mcp_server/services/scrapegraph_service.py`
- `build_server_command()` / `build_server_command_string()` are useful and should likely become the source of truth for `MCPServerStdio` config.
- Needs verification against how the actual local MCP server is launched today.
- Potential update: expose command as executable + args in a form directly consumable by OpenAI Agents SDK stdio MCP registration.

### `requirements.txt`
- Remove `anthropic`.
- Add the OpenAI Agents SDK dependency that provides MCP transport classes.
- Keep `openai`; Agents SDK does not replace the base OpenAI SDK if current Responses API code remains.

### `mcp_server/requirements.txt`
- Remove `anthropic`.
- Likely does not need Agents SDK unless the MCP server package itself will instantiate Agents clients; for a pure server, probably unnecessary.
- Keep `mcp`, `scrapegraph-py`, and current server-side libs.

## Additional files very likely needing edits beyond the minimum-read set
- Any app bootstrap / dependency wiring file that instantiates `OrchestrationService` with both OpenAI and Anthropic services.
- Any Anthropic service file and imports referenced by the app.
- Any config/env/docs referring to provider preference or Anthropic fallback.
- Likely `mcp_server/main` or equivalent entrypoint should be checked so the stdio launch command matches Agents SDK expectations exactly.

## Missing dependencies needed
- In root `requirements.txt`:
  - `openai-agents`
- Existing likely-required deps already present:
  - `openai`
  - `mcp`
- For SSE / streamable HTTP support:
  - No separate transport package is usually needed beyond the Agents SDK, but runtime compatibility depends on the installed Agents SDK version.
- In `mcp_server/requirements.txt`:
  - likely no new dependency required unless that package also becomes an Agents SDK client.

## Recommended transport mapping for this repo
- Local ScrapeGraph MCP: use OpenAI Agents SDK `MCPServerStdio`
  - Best match because repo already has local server command generation in `ScrapeGraphService`.
  - Avoids standing up extra HTTP infrastructure for local development.
- Remote/future MCP servers:
  - support config for both `MCPServerSse` and `MCPServerStreamableHttp`
  - Prefer streamable HTTP for newer remote deployments; keep SSE for compatibility with existing third-party MCP servers.

## Likely type/runtime issues
- `ScrapeGraphService()` raises at construction time if `SGAI_API_KEY` is absent.
  - `OrchestrationService.__init__` eagerly instantiates it, so app startup can fail even for non-scraping flows.
  - This will be more noticeable once orchestration becomes OpenAI-only and should likely be made lazy.
- `ScrapeGraphStdioClient` is not a real MCP transport client.
  - It exposes `list_tools()` / `call_tool()` in-process, but OpenAI Agents SDK MCP support expects MCP server objects, not this adapter.
- `build_server_command_string()` returns a shell string.
  - Agents SDK stdio registration may need command + args separately, not a shell-quoted single string. Verify exact constructor signature.
- Current `LLMServiceProtocol` models only direct text/structured methods.
  - Tool-enabled OpenAI agent execution will not fit neatly into the existing protocol without either:
    - extending the protocol, or
    - introducing a separate OpenAI agent/MCP service abstraction.
- `describe_routing_capabilities()` currently reports `"anthropic"` and a shell command string for ScrapeGraph.
  - Capability payload shape will need updating if the UI/API should expose transport type and MCP server metadata.
- Existing `OpenAIService.extract_structured()` uses Responses API JSON mode.
  - That is fine for non-tool structured extraction, but tool-calling through Agents SDK is a separate execution path and should not be conflated.
- Provider preference values may still include `"anthropic"` in callers or persisted config.
  - Once removed, invalid preference values must either map to `"openai"` or be ignored.

## Concrete implementation direction
- Keep `app/services/openai_service.py` for direct OpenAI Responses API work.
- Add a new focused service, e.g. `app/services/openai_agents_service.py`, to own:
  - MCP server config normalization
  - `MCPServerStdio` / `MCPServerSse` / `MCPServerStreamableHttp` creation
  - OpenAI agent execution with MCP tools
- Refactor `app/services/orchestration_service.py` to:
  - remove Anthropic entirely
  - route plain LLM tasks to `OpenAIService`
  - route MCP/tool tasks to the new OpenAI Agents service
- Use `mcp_server/services/scrapegraph_service.py` as the basis for local ScrapeGraph stdio server config, but likely expose structured command parts instead of only a shell string.