# OpenAI Agents SDK + MCP Integration / Remove Anthropic

## Tasks

- [x] 1. Create `app/services/openai_agents_service.py` (new OpenAI Agents SDK + MCP service)
- [x] 2. Update `requirements.txt` (remove `anthropic`, add `openai-agents`)
- [x] 3. Update `mcp_server/requirements.txt` (remove `anthropic`, add `openai-agents`)
- [x] 4. Update `app/core/config.py` (remove `anthropic_api_key`)
- [x] 5. Update `app/services/openai_service.py` (add `build_client()`, update descriptors)
- [x] 6. Update `app/services/orchestration_service.py` (remove Anthropic, add OpenAI Agents MCP)
- [x] 7. Update `app/api/routes/providers.py` (implement real endpoints)
- [x] 8. Update `app/services/pipeline_service.py` (remove Anthropic from mock data)
- [x] 9. Update `agent/services/pipeline.py` (remove Anthropic, OpenAI only)
- [x] 10. Update `agent/services/runner.py` (remove `run_anthropic_agent`)
- [x] 11. Update `analyzer/services/llm.py` (replace AnthropicLLMService with OpenAILLMService)
- [x] 12. Update `analyzer/services/pipeline.py` (use OpenAILLMService)
- [x] 13. Update `generator/services/providers.py` (remove Anthropic)
- [x] 14. Update `generator/services/pipeline.py` (remove Anthropic from provider loop)
- [x] 15. Update `generator/domain/models.py` (remove `anthropic_model` field)
- [x] 16. Delete `app/services/anthropic_service.py`
- [x] 17. Remove `anthropic` from `agent/`, `analyzer/`, `generator/`, `dashboard/` requirements.txt
- [x] 18. Update `.github/workflows/secrets-check.yml` (replace ANTHROPIC_API_KEY with SGAI_API_KEY)
- [x] 19. Update `app/services/dashboard_service.py` (remove Anthropic seed data)
- [x] 20. Install `openai-agents` package in `.venv` — verified imports OK

## Status: COMPLETE ✅

All Anthropic references removed from source code. OpenAI Agents SDK integrated with full
MCP transport support (stdio / sse / streamable_http) via `app/services/openai_agents_service.py`.
