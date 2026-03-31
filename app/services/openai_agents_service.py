from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any, Literal

from agents import Agent, Runner
from agents.mcp import MCPServerSse, MCPServerStdio, MCPServerStreamableHttp

MCPTransport = Literal["stdio", "sse", "streamable_http"]


# ---------------------------------------------------------------------------
# Config dataclasses – one per transport type
# ---------------------------------------------------------------------------


@dataclass
class MCPStdioConfig:
    """Parameters for a local subprocess MCP server (stdio transport)."""

    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | None = None


@dataclass
class MCPSseConfig:
    """Parameters for an HTTP+SSE MCP server."""

    url: str
    headers: dict[str, str] | None = None
    timeout: float = 5.0
    sse_read_timeout: float = 300.0


@dataclass
class MCPStreamableHttpConfig:
    """Parameters for a Streamable HTTP MCP server (preferred for remote)."""

    url: str
    headers: dict[str, str] | None = None
    timeout: float = 10.0
    sse_read_timeout: float = 300.0
    terminate_on_close: bool = True


@dataclass
class MCPServerConfig:
    """Transport-neutral MCP server descriptor used by OpenAIAgentsService."""

    name: str
    transport: MCPTransport
    enabled: bool = True
    cache_tools_list: bool = True
    max_retry_attempts: int = 3
    # Exactly one of the three config objects below must be set
    stdio: MCPStdioConfig | None = None
    sse: MCPSseConfig | None = None
    streamable_http: MCPStreamableHttpConfig | None = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class OpenAIAgentsService:
    """
    OpenAI Agents SDK service with full MCP transport support.

    Supports three MCP transports:
    - stdio        → MCPServerStdio   (local subprocess, e.g. ScrapeGraph)
    - sse          → MCPServerSse     (HTTP+SSE, legacy remote servers)
    - streamable_http → MCPServerStreamableHttp (preferred for new remote servers)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        mcp_servers: list[MCPServerConfig] | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._model = model or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
        self._mcp_servers: list[MCPServerConfig] = mcp_servers or []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key)

    @property
    def default_model(self) -> str:
        return self._model

    # ------------------------------------------------------------------
    # Default server configs
    # ------------------------------------------------------------------

    @classmethod
    def build_scrapegraph_stdio_config(cls) -> MCPServerConfig:
        """
        Build the default ScrapeGraph MCP server config using stdio transport.
        The local mcp_server/main.py FastMCP server is launched as a subprocess.
        """
        sgai_key = os.getenv("SGAI_API_KEY", "")
        env: dict[str, str] = {}
        if sgai_key:
            env["SGAI_API_KEY"] = sgai_key
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key:
            env["OPENAI_API_KEY"] = openai_key

        return MCPServerConfig(
            name="scrapegraph",
            transport="stdio",
            enabled=bool(sgai_key),
            cache_tools_list=True,
            stdio=MCPStdioConfig(
                command="python",
                args=["-m", "mcp_server.main"],
                env=env or None,
            ),
        )

    @classmethod
    def build_remote_sse_config(
        cls,
        *,
        name: str,
        url: str,
        token: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 5.0,
        sse_read_timeout: float = 300.0,
        enabled: bool = True,
    ) -> MCPServerConfig:
        """Build an SSE MCP server config for legacy remote servers."""
        merged_headers: dict[str, str] = {}
        if token:
            merged_headers["Authorization"] = f"Bearer {token}"
        if headers:
            merged_headers.update(headers)
        return MCPServerConfig(
            name=name,
            transport="sse",
            enabled=enabled,
            cache_tools_list=True,
            sse=MCPSseConfig(
                url=url,
                headers=merged_headers or None,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
            ),
        )

    @classmethod
    def build_remote_http_config(
        cls,
        *,
        name: str,
        url: str,
        token: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 10.0,
        sse_read_timeout: float = 300.0,
        terminate_on_close: bool = True,
        enabled: bool = True,
        max_retry_attempts: int = 3,
    ) -> MCPServerConfig:
        """Build a Streamable HTTP MCP server config (preferred for new remote servers)."""
        merged_headers: dict[str, str] = {}
        if token:
            merged_headers["Authorization"] = f"Bearer {token}"
        if headers:
            merged_headers.update(headers)
        return MCPServerConfig(
            name=name,
            transport="streamable_http",
            enabled=enabled,
            cache_tools_list=True,
            max_retry_attempts=max_retry_attempts,
            streamable_http=MCPStreamableHttpConfig(
                url=url,
                headers=merged_headers or None,
                timeout=timeout,
                sse_read_timeout=sse_read_timeout,
                terminate_on_close=terminate_on_close,
            ),
        )

    # ------------------------------------------------------------------
    # Internal factory
    # ------------------------------------------------------------------

    def _build_mcp_server_object(
        self, config: MCPServerConfig
    ) -> MCPServerStdio | MCPServerSse | MCPServerStreamableHttp:
        """Convert an MCPServerConfig into the matching OpenAI Agents SDK object."""
        if config.transport == "stdio":
            if not config.stdio:
                raise ValueError(
                    f"MCPServerConfig '{config.name}' has transport='stdio' but no stdio config."
                )
            params: dict[str, Any] = {
                "command": config.stdio.command,
                "args": config.stdio.args,
            }
            if config.stdio.env:
                params["env"] = config.stdio.env
            if config.stdio.cwd:
                params["cwd"] = config.stdio.cwd
            return MCPServerStdio(
                params=params,
                cache_tools_list=config.cache_tools_list,
                name=config.name,
            )

        if config.transport == "sse":
            if not config.sse:
                raise ValueError(
                    f"MCPServerConfig '{config.name}' has transport='sse' but no sse config."
                )
            params = {"url": config.sse.url}
            if config.sse.headers:
                params["headers"] = config.sse.headers
            params["timeout"] = config.sse.timeout
            params["sse_read_timeout"] = config.sse.sse_read_timeout
            return MCPServerSse(
                params=params,
                cache_tools_list=config.cache_tools_list,
                name=config.name,
            )

        if config.transport == "streamable_http":
            if not config.streamable_http:
                raise ValueError(
                    f"MCPServerConfig '{config.name}' has transport='streamable_http' "
                    "but no streamable_http config."
                )
            params = {"url": config.streamable_http.url}
            if config.streamable_http.headers:
                params["headers"] = config.streamable_http.headers
            params["timeout"] = config.streamable_http.timeout
            params["sse_read_timeout"] = config.streamable_http.sse_read_timeout
            params["terminate_on_close"] = config.streamable_http.terminate_on_close
            return MCPServerStreamableHttp(
                params=params,
                cache_tools_list=config.cache_tools_list,
                name=config.name,
                max_retry_attempts=config.max_retry_attempts,
            )

        raise ValueError(f"Unknown MCP transport: '{config.transport}'")

    # ------------------------------------------------------------------
    # Agent execution
    # ------------------------------------------------------------------

    async def run_agent_async(
        self,
        *,
        prompt: str,
        instructions: str | None = None,
        mcp_server_configs: list[MCPServerConfig] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Run an OpenAI agent with MCP tools asynchronously.

        Uses AsyncExitStack to manage multiple MCP server context managers cleanly.
        Falls back to a plain agent (no MCP) when no enabled servers are provided.
        """
        effective_model = model or self._model
        effective_instructions = instructions or (
            "You are a helpful job search assistant. "
            "Use the available tools to answer questions about job offers, companies, and career strategy."
        )
        configs = [c for c in (mcp_server_configs or self._mcp_servers) if c.enabled]

        if not configs:
            # Plain agent without MCP tools
            agent = Agent(
                name="job-bot-agent",
                instructions=effective_instructions,
                model=effective_model,
            )
            result = await Runner.run(agent, prompt)
            return {
                "provider": "openai_agents",
                "model": effective_model,
                "text": result.final_output,
                "mcp_servers": [],
            }

        async with AsyncExitStack() as stack:
            active_servers = [
                await stack.enter_async_context(self._build_mcp_server_object(c))
                for c in configs
            ]
            agent = Agent(
                name="job-bot-agent",
                instructions=effective_instructions,
                model=effective_model,
                mcp_servers=active_servers,
            )
            result = await Runner.run(agent, prompt)
            return {
                "provider": "openai_agents",
                "model": effective_model,
                "text": result.final_output,
                "mcp_servers": [c.name for c in configs],
            }

    def run_agent(
        self,
        *,
        prompt: str,
        instructions: str | None = None,
        mcp_server_configs: list[MCPServerConfig] | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """Synchronous wrapper around run_agent_async."""
        return asyncio.run(
            self.run_agent_async(
                prompt=prompt,
                instructions=instructions,
                mcp_server_configs=mcp_server_configs,
                model=model,
            )
        )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def describe_mcp_servers(self) -> list[dict[str, Any]]:
        """Return metadata about all registered MCP server configs."""
        result = []
        for c in self._mcp_servers:
            entry: dict[str, Any] = {
                "name": c.name,
                "transport": c.transport,
                "enabled": c.enabled,
                "cache_tools_list": c.cache_tools_list,
            }
            if c.transport == "stdio" and c.stdio:
                entry["command"] = c.stdio.command
                entry["args"] = c.stdio.args
            elif c.transport == "sse" and c.sse:
                entry["url"] = c.sse.url
            elif c.transport == "streamable_http" and c.streamable_http:
                entry["url"] = c.streamable_http.url
                entry["max_retry_attempts"] = c.max_retry_attempts
            result.append(entry)
        return result

    def get_capability_descriptors(self) -> list[dict[str, Any]]:
        return [
            {
                "provider": "openai_agents",
                "operation": "run_agent_with_mcp",
                "available": self.is_configured,
                "model": self._model,
                "transports_supported": ["stdio", "sse", "streamable_http"],
                "strengths": [
                    "tool-enabled agent execution via MCP",
                    "web scraping and extraction via ScrapeGraph MCP (stdio)",
                    "remote MCP server integration via SSE or Streamable HTTP",
                    "multi-server orchestration with AsyncExitStack",
                ],
                "best_for": [
                    "job offer scraping and structured extraction",
                    "company research with web search",
                    "multi-step agentic workflows with external tools",
                ],
                "mcp_servers": self.describe_mcp_servers(),
            }
        ]


# ---------------------------------------------------------------------------
# Default singleton with ScrapeGraph stdio server pre-registered
# ---------------------------------------------------------------------------

openai_agents_service = OpenAIAgentsService(
    mcp_servers=[OpenAIAgentsService.build_scrapegraph_stdio_config()],
)
