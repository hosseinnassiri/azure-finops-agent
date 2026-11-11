"""The Claude Code plugin (plugins/roastbot) must stay in sync with the agent it mirrors."""

import json
import re
from pathlib import Path

from roastbot import agent

PLUGIN = Path(__file__).parent.parent / "plugins" / "roastbot"


def test_skill_persona_matches_agent():
	skill = (PLUGIN / "skills" / "roast" / "SKILL.md").read_text(encoding="utf-8")
	persona = re.search(r"```persona\n(.*?)```", skill, re.S).group(1)
	assert persona == agent.PERSONA


def test_plugin_mcp_server_matches_agent():
	config = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
	server = agent.azure_mcp_server()
	assert config["mcpServers"]["azure"] == {
		"type": server["type"],
		"command": server["command"],
		"args": server["args"],
	}
	assert "--read-only" in server["args"]


def test_skill_pins_the_package_version():
	skill = (PLUGIN / "skills" / "roast" / "SKILL.md").read_text(encoding="utf-8")
	plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
	pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text(encoding="utf-8")
	version = re.search(r'^version = "(.+)"', pyproject, re.M).group(1)
	assert plugin["version"] == version
	assert skill.count(f"azure-finops-agent@v{version} roastbot") == 3  # allowed-tools (Bash, PowerShell), ROASTBOT
