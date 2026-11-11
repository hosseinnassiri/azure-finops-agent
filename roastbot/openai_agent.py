"""RoastBot on any OpenAI-compatible Chat Completions endpoint: Azure OpenAI / Foundry, OpenAI, Ollama, vLLM...

The Claude engine (agent.py) gets its tool loop from the Claude Agent SDK. This is the same agent with our own
loop: same persona and task, same read-only Azure MCP server, same RoastTools. The model can only call the
tools registered here; any other name gets an error back. There is no shell and no file access.

Configuration is the openai SDK's own: OPENAI_BASE_URL and OPENAI_API_KEY. With no key and an Azure endpoint,
it signs in with Entra ID through DefaultAzureCredential (your `az login`, or the managed identity).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
from collections.abc import Awaitable, Callable
from functools import partial
from typing import Any
from urllib.parse import urlparse

import openai
from azure.identity import get_bearer_token_provider
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import PaginatedRequestParams
from openai import AsyncOpenAI

from . import agent, cloud

AZURE_HOSTS = (".openai.azure.com", ".services.ai.azure.com", ".cognitiveservices.azure.com")
AZURE_SCOPE = "https://ai.azure.com/.default"
TOOL_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")  # what Chat Completions accepts as a function name
MAX_RESULT_CHARS = 30_000  # activity logs get huge, and smaller models have smaller context windows
MAX_TURNS = 60
CONTENT_FILTER = (
	"\n[agent stopped: the provider's content filter blocked the response. RoastBot's persona is deliberately "
	"profane; on Azure OpenAI, ask for a deployment with a less strict content filter, or tone down PERSONA.]"
)

Handler = Callable[[dict[str, Any]], Awaitable[tuple[str, bool]]]
Tools = dict[str, tuple[dict, Handler]]  # function name -> (Chat Completions tool spec, handler)


def make_client() -> AsyncOpenAI:
	base_url = os.environ.get("OPENAI_BASE_URL")
	if os.environ.get("OPENAI_API_KEY"):
		return AsyncOpenAI(base_url=base_url)
	if (urlparse(base_url or "").hostname or "").endswith(AZURE_HOSTS):
		fetch_token = get_bearer_token_provider(cloud.credential(), AZURE_SCOPE)

		async def token() -> str:
			return await asyncio.to_thread(fetch_token)

		return AsyncOpenAI(base_url=base_url, api_key=token)
	raise agent.ProviderError(
		"--provider openai needs OPENAI_API_KEY, or OPENAI_BASE_URL pointing at an Azure OpenAI / Foundry endpoint "
		"(https://<resource>.openai.azure.com/openai/v1/) to sign in with az login."
	)


def function_spec(name: str, description: str | None, schema: dict | None) -> dict:
	parameters = schema or agent.NO_ARGS
	return {"type": "function", "function": {"name": name, "description": description or "", "parameters": parameters}}


def mcp_text(result: Any) -> str:
	parts = [c.text for c in getattr(result, "content", None) or [] if getattr(c, "type", None) == "text"]
	return "\n".join(parts) or "(no text content)"


async def list_mcp_tools(session: ClientSession) -> list:
	tools, cursor = [], None
	while True:
		page = await session.list_tools(params=PaginatedRequestParams(cursor=cursor) if cursor else None)
		tools += page.tools
		cursor = page.next_cursor
		if not cursor:
			return tools


def mcp_tools(session: ClientSession, listed: list) -> Tools:
	registry: Tools = {}
	for t in listed:
		if not TOOL_NAME.match(t.name):
			print(f"  skipping Azure MCP tool with an unusable name: {t.name}", file=sys.stderr)
			continue

		async def handler(args: dict[str, Any], name: str = t.name) -> tuple[str, bool]:
			result = await session.call_tool(name, args)
			return mcp_text(result), bool(getattr(result, "is_error", False))

		registry[t.name] = (function_spec(t.name, t.description, t.input_schema), handler)
	return registry


def roast_tools(tools: agent.RoastTools) -> Tools:
	"""Registered under the names the Claude engine uses, so ROAST_TASK reads the same on both."""
	return {
		f"mcp__roastbot__{name}": (function_spec(f"mcp__roastbot__{name}", desc, schema), partial(tools.call, name))
		for name, (desc, schema) in agent.ROASTBOT_TOOLS.items()
	}


def cap(text: str) -> str:
	if len(text) <= MAX_RESULT_CHARS:
		return text
	return f"{text[:MAX_RESULT_CHARS]}\n[truncated {len(text) - MAX_RESULT_CHARS:,} characters]"


async def dispatch(tools: Tools, call: Any) -> str:
	name = call.function.name
	print(f"  🔧 {name.removeprefix('mcp__')}")
	if name not in tools:
		return f"ERROR: no tool named {name!r}. Available: {', '.join(tools)}"
	try:
		args = json.loads(call.function.arguments or "{}")
	except json.JSONDecodeError as exc:
		return f"ERROR: arguments aren't valid JSON ({exc}). Call it again with a JSON object."
	if not isinstance(args, dict):
		return "ERROR: arguments must be a JSON object."
	try:
		text, is_error = await tools[name][1](args)
	except Exception as exc:  # a failing tool is the model's problem to work around, not a crash
		text, is_error = f"{type(exc).__name__}: {exc}", True
	return cap(f"ERROR: {text}" if is_error else text)


async def run(client: Any, model: str, messages: list[dict], tools: Tools, max_turns: int = MAX_TURNS) -> str:
	"""The tool loop. Returns why it stopped: "done", "content_filter" or "max_turns"."""
	specs = [spec for spec, _ in tools.values()]
	for _ in range(max_turns):
		try:
			response = await client.chat.completions.create(model=model, messages=messages, tools=specs)
		except openai.BadRequestError as exc:
			if exc.code != "content_filter":
				raise
			print(CONTENT_FILTER)
			return "content_filter"
		choice = response.choices[0]
		message = choice.message
		for text in (message.content, getattr(message, "refusal", None)):
			if text and text.strip():
				print(text)
		calls = message.tool_calls or []
		messages.append(
			{
				"role": "assistant",
				"content": message.content,
				**({"tool_calls": [assistant_call(c) for c in calls]} if calls else {}),
			}
		)
		if choice.finish_reason == "content_filter":
			print(CONTENT_FILTER)
			return "content_filter"
		if not calls:
			return "done"
		results = await asyncio.gather(*(dispatch(tools, c) for c in calls))
		messages += [{"role": "tool", "tool_call_id": c.id, "content": r} for c, r in zip(calls, results, strict=True)]
	print(f"\n[agent stopped: hit {max_turns} turns]")
	return "max_turns"


def assistant_call(call: Any) -> dict:
	return {
		"id": call.id,
		"type": "function",
		"function": {"name": call.function.name, "arguments": call.function.arguments},
	}


async def roast(task: str, tools: agent.RoastTools, model: str | None) -> None:
	if not model:
		raise agent.ProviderError("--provider openai needs --model: your model or deployment name.")
	client = make_client()
	server = agent.azure_mcp_server()
	# Pass the full environment: mcp's default strips AZURE_* (managed identity, tenant) that Azure MCP needs.
	params = StdioServerParameters(command=server["command"], args=server["args"], env=dict(os.environ))
	async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
		await session.initialize()
		registry = {**mcp_tools(session, await list_mcp_tools(session)), **roast_tools(tools)}
		messages = [{"role": "system", "content": agent.PERSONA}, {"role": "user", "content": task}]
		await run(client, model, messages, registry)
