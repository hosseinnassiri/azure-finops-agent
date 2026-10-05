import asyncio
import json
from types import SimpleNamespace

import pytest

from roastbot import agent, openai_agent


def call(id_, name, arguments):
	return SimpleNamespace(id=id_, function=SimpleNamespace(name=name, arguments=arguments))


def reply(content=None, calls=None, finish="stop"):
	message = SimpleNamespace(content=content, refusal=None, tool_calls=calls)
	return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=finish)])


class ScriptedClient:
	"""Replays canned chat completions and records what the loop sent each turn."""

	def __init__(self, *replies):
		self.replies, self.sent = list(replies), []
		self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

	async def create(self, model, messages, tools):
		self.sent.append({"messages": [dict(m) for m in messages], "tools": [t["function"]["name"] for t in tools]})
		return self.replies.pop(0)


def echo_tools(**handlers):
	async def wrap(fn, args):
		return fn(args)

	return {
		name: (openai_agent.function_spec(name, "", None), lambda args, fn=fn: wrap(fn, args))
		for name, fn in handlers.items()
	}


def test_loop_runs_parallel_tool_calls_and_stops_without_calls():
	client = ScriptedClient(
		reply("Hunting.", [call("1", "a", '{"x": 1}'), call("2", "b", "{}")], finish="tool_calls"),
		reply("Done roasting."),
	)
	tools = echo_tools(a=lambda args: (f"a got {args['x']}", False), b=lambda args: ("b failed", True))
	messages = [{"role": "user", "content": "go"}]

	assert asyncio.run(openai_agent.run(client, "m", messages, tools)) == "done"
	assert client.sent[0]["tools"] == ["a", "b"]
	assert messages[1]["tool_calls"][0] == {
		"id": "1",
		"type": "function",
		"function": {"name": "a", "arguments": '{"x": 1}'},
	}
	assert messages[2:4] == [
		{"role": "tool", "tool_call_id": "1", "content": "a got 1"},
		{"role": "tool", "tool_call_id": "2", "content": "ERROR: b failed"},
	]
	assert messages[-1] == {"role": "assistant", "content": "Done roasting."}


def test_unknown_tools_bad_json_and_crashes_go_back_to_the_model():
	def boom(args):
		raise RuntimeError("kaboom")

	tools = echo_tools(boom=boom)
	calls = [call("1", "bash", "{}"), call("2", "boom", "{not json"), call("3", "boom", "[1]"), call("4", "boom", "{}")]
	client = ScriptedClient(reply(calls=calls), reply("ok"))
	messages = []
	asyncio.run(openai_agent.run(client, "m", messages, tools))
	results = [m["content"] for m in messages if m["role"] == "tool"]
	assert results[0].startswith("ERROR: no tool named 'bash'")
	assert results[1].startswith("ERROR: arguments aren't valid JSON")
	assert results[2] == "ERROR: arguments must be a JSON object."
	assert results[3] == "ERROR: RuntimeError: kaboom"


def test_content_filter_and_turn_limit_stop_the_loop():
	assert (
		asyncio.run(openai_agent.run(ScriptedClient(reply(finish="content_filter")), "m", [], {})) == "content_filter"
	)
	looping = ScriptedClient(*[reply(calls=[call(str(i), "a", "{}")]) for i in range(3)])
	assert (
		asyncio.run(openai_agent.run(looping, "m", [], echo_tools(a=lambda a: ("", False)), max_turns=3)) == "max_turns"
	)


def test_long_results_are_truncated():
	text = openai_agent.cap("x" * (openai_agent.MAX_RESULT_CHARS + 5))
	assert text.endswith("[truncated 5 characters]")


def test_mcp_tools_become_function_specs_and_bad_names_are_skipped():
	class Session:
		async def call_tool(self, name, args):
			return SimpleNamespace(content=[SimpleNamespace(type="text", text=f"{name}:{args}")], is_error=False)

	listed = [
		SimpleNamespace(
			name="compute_vm_get", description="Get a VM", input_schema={"type": "object", "properties": {}}
		),
		SimpleNamespace(name="has spaces", description="", input_schema=None),
	]
	tools = openai_agent.mcp_tools(Session(), listed)
	assert list(tools) == ["compute_vm_get"]
	spec, handler = tools["compute_vm_get"]
	assert spec["function"]["description"] == "Get a VM"
	assert asyncio.run(handler({"vm": "x"})) == ("compute_vm_get:{'vm': 'x'}", False)


def test_roast_tools_use_the_claude_names(tmp_path):
	(tmp_path / "findings.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
	tools = openai_agent.roast_tools(agent.RoastTools(tmp_path, None, {}, use_guard=False))
	assert set(tools) == {f"mcp__roastbot__{n}" for n in agent.ROASTBOT_TOOLS}
	text, is_error = asyncio.run(tools["mcp__roastbot__save_roasts"][1]({"roasts_json": "{}"}))
	assert text.startswith("Saved.") and not is_error


def test_auth_uses_key_then_entra_for_azure_then_gives_up(monkeypatch):
	built = []
	monkeypatch.setattr(openai_agent, "AsyncOpenAI", lambda **kwargs: built.append(kwargs) or kwargs)
	monkeypatch.setattr(openai_agent.cloud, "credential", lambda: "cred")
	monkeypatch.setattr(openai_agent, "get_bearer_token_provider", lambda cred, scope: lambda: f"token:{cred}:{scope}")

	monkeypatch.delenv("OPENAI_API_KEY", raising=False)
	monkeypatch.setenv("OPENAI_BASE_URL", "https://contoso.openai.azure.com/openai/v1/")
	entra = openai_agent.make_client()
	assert entra["base_url"] == "https://contoso.openai.azure.com/openai/v1/"
	assert asyncio.run(entra["api_key"]()) == f"token:cred:{openai_agent.AZURE_SCOPE}"

	monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
	assert "api_key" not in openai_agent.make_client()  # the SDK reads OPENAI_API_KEY itself

	monkeypatch.delenv("OPENAI_API_KEY")
	monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
	with pytest.raises(agent.ProviderError, match="OPENAI_API_KEY"):
		openai_agent.make_client()
