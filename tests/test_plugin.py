"""The Claude Code plugin (plugins/roastbot) must stay in sync with the agent it mirrors."""

import json
import os
import re
import runpy
from pathlib import Path

import pytest

from roastbot import agent

ROOT = Path(__file__).parent.parent
PLUGIN = ROOT / "plugins" / "roastbot"
RUN = "uv run --locked --no-editable --isolated --project ${CLAUDE_PLUGIN_ROOT}/app roastbot"


def test_skill_persona_matches_agent():
	skill = (PLUGIN / "skills" / "roast" / "SKILL.md").read_text(encoding="utf-8")
	persona = re.search(r"```persona\n(.*?)```", skill, re.S).group(1)
	assert persona == agent.PERSONA


def test_plugin_mcp_server_matches_agent():
	server = agent.azure_mcp_server()
	for path in (PLUGIN / ".mcp.json", ROOT / ".mcp.json"):  # the plugin's and this repo's
		assert json.loads(path.read_text(encoding="utf-8"))["mcpServers"]["azure"] == server, path
	assert "--read-only" in server["args"]
	assert server["env"]["AZURE_MCP_COLLECT_TELEMETRY"] == "false"  # the plugin README promises no telemetry


def test_versions_match():
	version = re.search(r'^version = "(.+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
	plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
	app = (PLUGIN / "app" / "pyproject.toml").read_text(encoding="utf-8")
	assert plugin["version"] == version
	assert f'version = "{version}"' in app


def test_skill_runs_only_the_bundled_scan_and_report():
	skill = (PLUGIN / "skills" / "roast" / "SKILL.md").read_text(encoding="utf-8")
	assert "uvx" not in skill and "git+" not in skill  # the code ships inside the plugin
	allowed = re.search(r"^allowed-tools: (.*)$", skill, re.M).group(1)
	shell_rules = re.findall(r"(?:Bash|PowerShell)\(([^)]*)\)", allowed)
	assert len(shell_rules) == 4
	for rule in shell_rules:
		assert re.fullmatch(re.escape(RUN) + r" --out roastbot-out (scan|report) \*", rule), rule
	assert re.findall(r"\b(Read|Edit|Write)\(([^)]*)\)", allowed) == [
		("Read", "./roastbot-out/**"),
		("Edit", "./roastbot-out/**"),
	]


def test_bundle_is_the_read_only_slice():
	bump = runpy.run_path(str(ROOT / "scripts" / "bump_version.py"))
	bundled = sorted(p.stem for p in (PLUGIN / "app" / "roastbot").glob("*.py"))
	assert bundled == sorted(bump["BUNDLE"])
	assert not {"agent", "demo", "openai_agent"} & set(bundled)  # no SDK engines, nothing that writes to Azure
	for path in (PLUGIN / "app" / "roastbot").glob("*.py"):
		assert "subprocess" not in path.read_text(encoding="utf-8"), path
	names = lambda text: set(re.findall(r'^\s+"([a-z0-9-]+)[<>=~!]', text, re.M))  # noqa: E731
	app_deps = names((PLUGIN / "app" / "pyproject.toml").read_text(encoding="utf-8"))
	assert app_deps and app_deps <= names((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


@pytest.mark.skipif(not os.environ.get("ROASTBOT_RELEASE"), reason="the release job syncs the bundle, then checks it")
def test_bundle_matches_the_source():
	for path in (PLUGIN / "app" / "roastbot").glob("*.py"):
		source = (ROOT / "roastbot" / path.name).read_text(encoding="utf-8")
		assert path.read_text(encoding="utf-8") == source, path


def test_plugin_ships_the_license():
	# Installs copy only plugins/roastbot, and Anthropic's directory scans only that folder.
	assert (PLUGIN / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()
	plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
	assert plugin["license"] == "Apache-2.0"
	assert 'license = "Apache-2.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
