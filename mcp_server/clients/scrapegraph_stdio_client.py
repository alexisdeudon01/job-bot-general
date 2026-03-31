from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mcp_server.services.scrapegraph_service import ScrapeGraphService


@dataclass(frozen=True)
class StdioToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


class ScrapeGraphStdioClient:
    """Transport-oriented adapter exposing ScrapeGraph capabilities as stdio-callable tools."""

    def __init__(self, service: ScrapeGraphService | None = None) -> None:
        self._service = service or ScrapeGraphService()
        self._tools: dict[str, StdioToolSpec] = {
            "markdownify": StdioToolSpec(
                name="markdownify",
                description="Transform any webpage into clean, structured markdown format.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "website_url": {"type": "string"},
                    },
                    "required": ["website_url"],
                },
            ),
            "smartscraper": StdioToolSpec(
                name="smartscraper",
                description="Extract structured data from a webpage using a natural-language prompt.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "website_url": {"type": "string"},
                        "user_prompt": {"type": "string"},
                        "output_schema": {"type": "object"},
                        "number_of_scrolls": {"type": "integer"},
                        "markdown_only": {"type": "boolean"},
                    },
                    "required": ["website_url", "user_prompt"],
                },
            ),
            "searchscraper": StdioToolSpec(
                name="searchscraper",
                description="Search the web and return structured extraction results across multiple sources.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "user_prompt": {"type": "string"},
                        "num_results": {"type": "integer"},
                        "number_of_scrolls": {"type": "integer"},
                        "time_range": {"type": "string"},
                        "output_schema": {"type": "object"},
                    },
                    "required": ["user_prompt"],
                },
            ),
            "scrape": StdioToolSpec(
                name="scrape",
                description="Fetch page content with optional heavy JavaScript rendering.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "website_url": {"type": "string"},
                        "render_heavy_js": {"type": "boolean"},
                    },
                    "required": ["website_url"],
                },
            ),
            "sitemap": StdioToolSpec(
                name="sitemap",
                description="Extract sitemap URLs and structure for a website.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "website_url": {"type": "string"},
                    },
                    "required": ["website_url"],
                },
            ),
            "smartcrawler_initiate": StdioToolSpec(
                name="smartcrawler_initiate",
                description="Initiate intelligent multi-page web crawling asynchronously.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "prompt": {"type": "string"},
                        "extraction_mode": {"type": "string"},
                        "depth": {"type": "integer"},
                        "max_pages": {"type": "integer"},
                        "same_domain_only": {"type": "boolean"},
                    },
                    "required": ["url"],
                },
            ),
            "smartcrawler_fetch_results": StdioToolSpec(
                name="smartcrawler_fetch_results",
                description="Retrieve results from an asynchronous smart crawler request.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "request_id": {"type": "string"},
                    },
                    "required": ["request_id"],
                },
            ),
            "agentic_scrapper": StdioToolSpec(
                name="agentic_scrapper",
                description="Run advanced agentic scraping workflows with optional schema and steps.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "user_prompt": {"type": "string"},
                        "output_schema": {"type": "object"},
                        "steps": {"type": "array"},
                        "ai_extraction": {"type": "boolean"},
                        "persistent_session": {"type": "boolean"},
                        "timeout_seconds": {"type": "number"},
                    },
                    "required": ["url"],
                },
            ),
            "scrapegraph_markdownify": StdioToolSpec(
                name="scrapegraph_markdownify",
                description="Convert a web page into markdown for downstream extraction or prompting.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                    },
                    "required": ["url"],
                },
            ),
            "scrapegraph_extract": StdioToolSpec(
                name="scrapegraph_extract",
                description="Extract structured data from a web page using a caller-provided prompt and optional schema.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "prompt": {"type": "string"},
                        "schema": {"type": "object"},
                    },
                    "required": ["url", "prompt"],
                },
            ),
            "scrapegraph_search_extract": StdioToolSpec(
                name="scrapegraph_search_extract",
                description="Search across the web and extract structured data using a caller-provided prompt and optional schema.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string"},
                        "schema": {"type": "object"},
                        "num_results": {"type": "integer"},
                        "time_range": {"type": "string"},
                        "location": {"type": "string"},
                    },
                    "required": ["prompt"],
                },
            ),
        }

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            for tool in self._tools.values()
        ]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = arguments or {}
        if name == "markdownify":
            return self._service.markdownify_job_page(payload["website_url"])
        if name == "smartscraper":
            return self._service.extract(
                url=payload["website_url"],
                user_prompt=payload["user_prompt"],
                output_schema=payload.get("output_schema"),
            )
        if name == "searchscraper":
            request_payload: dict[str, Any] = {
                "user_prompt": payload["user_prompt"],
            }
            if payload.get("output_schema") is not None:
                request_payload["output_schema"] = payload["output_schema"]
            if payload.get("num_results") is not None:
                request_payload["num_results"] = payload["num_results"]
            if payload.get("number_of_scrolls") is not None:
                request_payload["number_of_scrolls"] = payload["number_of_scrolls"]
            if payload.get("time_range") is not None:
                request_payload["time_range"] = payload["time_range"]
            return self._service.search_extract(request_payload)
        if name == "scrape":
            return {
                "tool": "scrape",
                "supported": False,
                "available_in_registry": True,
                "detail": "This tool is listed from ScrapeGraph MCP but is not yet implemented through scrapegraph_py in this project.",
                "arguments": payload,
            }
        if name == "sitemap":
            return {
                "tool": "sitemap",
                "supported": False,
                "available_in_registry": True,
                "detail": "This tool is listed from ScrapeGraph MCP but is not yet implemented through scrapegraph_py in this project.",
                "arguments": payload,
            }
        if name == "smartcrawler_initiate":
            return {
                "tool": "smartcrawler_initiate",
                "supported": False,
                "available_in_registry": True,
                "detail": "This tool is listed from ScrapeGraph MCP but is not yet implemented through scrapegraph_py in this project.",
                "arguments": payload,
            }
        if name == "smartcrawler_fetch_results":
            return {
                "tool": "smartcrawler_fetch_results",
                "supported": False,
                "available_in_registry": True,
                "detail": "This tool is listed from ScrapeGraph MCP but is not yet implemented through scrapegraph_py in this project.",
                "arguments": payload,
            }
        if name == "agentic_scrapper":
            return {
                "tool": "agentic_scrapper",
                "supported": False,
                "available_in_registry": True,
                "detail": "This tool is listed from ScrapeGraph MCP but is not yet implemented through scrapegraph_py in this project.",
                "arguments": payload,
            }
        if name == "scrapegraph_markdownify":
            return self._service.markdownify_job_page(payload["url"])
        if name == "scrapegraph_extract":
            return self._service.extract(
                url=payload["url"],
                user_prompt=payload["prompt"],
                output_schema=payload.get("schema"),
            )
        if name == "scrapegraph_search_extract":
            request_payload: dict[str, Any] = {
                "user_prompt": payload["prompt"],
            }
            if payload.get("schema") is not None:
                request_payload["output_schema"] = payload["schema"]
            if payload.get("num_results") is not None:
                request_payload["num_results"] = payload["num_results"]
            if payload.get("time_range") is not None:
                request_payload["time_range"] = payload["time_range"]
            if payload.get("location") is not None:
                request_payload["location_geo_code"] = payload["location"]
            return self._service.search_extract(request_payload)
        raise ValueError(f"Unknown tool: {name}")
