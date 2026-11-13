"""The Claude Code plugins must stay in sync with the agent they mirror.

plugins/roastbot-full is the marketplace plugin: bundled code, a read-only Azure MCP server, pre-approved tools.
plugins/roastbot is the Anthropic directory's copy, which may only hold docs and images (the directory refuses code,
local MCP servers and pre-approved tools from organizations it hasn't Verified): its skill runs the full plugin's
bundle with uvx from a pinned commit.
"""

import json
import os
import re
import runpy
import subprocess
from pathlib import Path

import pytest

from roastbot import agent, style

ROOT = Path(__file__).parent.parent
PLUGIN = ROOT / "plugins" / "roastbot-full"
DIRECTORY = ROOT / "plugins" / "roastbot"
DIRECTORY_SKILL = DIRECTORY / "skills" / "roast" / "SKILL.md"
RUN = "uv run --locked --no-editable --isolated --project ${CLAUDE_PLUGIN_ROOT}/app roastbot"


@pytest.mark.parametrize(
	"skill", [PLUGIN / "skills" / "roast" / "SKILL.md", DIRECTORY_SKILL], ids=["full", "directory"]
)
def test_skill_persona_matches_agent(skill):
	persona = re.search(r"```persona\n(.*?)```", skill.read_text(encoding="utf-8"), re.S).group(1)
	assert persona == agent.PERSONA


@pytest.mark.parametrize(
	"skill", [PLUGIN / "skills" / "roast" / "SKILL.md", DIRECTORY_SKILL], ids=["full", "directory"]
)
def test_skill_style_guide_matches_agent(skill):
	guide = re.search(r"```style\n(.*?)```", skill.read_text(encoding="utf-8"), re.S).group(1)
	assert guide == style.render()  # every example; the agent rotates them


def test_skills_share_their_safety_rules_and_steps():
	full = (PLUGIN / "skills" / "roast" / "SKILL.md").read_text(encoding="utf-8")
	directory = DIRECTORY_SKILL.read_text(encoding="utf-8")
	steps = "3. **Write the verdicts**"
	assert full[full.index(steps) :] == directory[directory.index(steps) :]
	first_rules = lambda text: text[text.index("## Safety rules") :].split("\n")[:7]  # noqa: E731
	assert first_rules(full) == first_rules(directory)  # never change Azure, never run a fix_command


def test_plugin_mcp_server_matches_agent():
	server = agent.azure_mcp_server()
	assert json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["azure"] == server
	assert "--read-only" in server["args"]
	assert server["env"]["AZURE_MCP_COLLECT_TELEMETRY"] == "false"  # the plugin README promises no telemetry
	# The plugin starts the same azmcp command from a locked uv project (the directory rejects a bare PyPI pin).
	plugin = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["azure"]
	azmcp = server["args"][server["args"].index("azmcp") :]
	assert plugin["command"] == "uv"
	assert plugin["args"] == ["run", "--locked", "--isolated", "--project", "${CLAUDE_PLUGIN_ROOT}/mcp", *azmcp]
	assert plugin["env"] == server["env"]
	pinned = (PLUGIN / "mcp" / "pyproject.toml").read_text(encoding="utf-8")
	assert f'dependencies = ["{agent.AZMCP_VERSION}"]' in pinned
	lock = (PLUGIN / "mcp" / "uv.lock").read_text(encoding="utf-8")
	assert f'name = "msmcp-azure"\nversion = "{agent.AZMCP_VERSION.split("==")[1]}"' in lock


def test_versions_match():
	version = re.search(r'^version = "(.+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
	plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
	app = (PLUGIN / "app" / "pyproject.toml").read_text(encoding="utf-8")
	assert plugin["version"] == version
	directory = json.loads((DIRECTORY / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
	assert directory == plugin  # same name, version and listing details
	assert f'version = "{version}"' in app


def test_skill_runs_only_the_bundled_scan_and_report():
	skill = (PLUGIN / "skills" / "roast" / "SKILL.md").read_text(encoding="utf-8")
	assert "uvx" not in skill and "git+" not in skill  # the code ships inside the plugin
	allowed = re.search(r"^allowed-tools: (.*)$", skill, re.M).group(1)
	shell_rules = re.findall(r"(?:Bash|PowerShell)\(([^)]*)\)", allowed)
	assert len(shell_rules) == 4
	for rule in shell_rules:
		assert re.fullmatch(re.escape(RUN) + r" --out roastbot-out (scan|report) \*", rule), rule
	mcp = re.findall(r"mcp__plugin_roastbot_azure\w*", allowed)
	assert "mcp__plugin_roastbot_azure" not in mcp  # exact tools, never the whole server
	named = {
		f"mcp__plugin_roastbot_azure__{t}" for t in re.findall(r"`((?:monitor|compute|advisor|pricing)_\w+)`", skill)
	}
	assert set(mcp) == named  # every tool the steps call, and nothing else
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


# What the directory accepts from an organization it hasn't Verified: docs and images, nothing that runs.
ALLOWED_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}


def test_directory_plugin_ships_nothing_that_runs():
	files = [p for p in DIRECTORY.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
	assert files
	for path in files:
		assert path.suffix.lower() in ALLOWED_SUFFIXES or path.name == "LICENSE", path
		data = path.read_bytes()
		assert not data.startswith(b"#!"), path
		if path.suffix.lower() not in IMAGES:
			assert b"\x00" not in data, path
			data.decode("utf-8")
	assert not (DIRECTORY / ".mcp.json").exists() and not (DIRECTORY / "hooks").exists()
	manifest = json.loads((DIRECTORY / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
	assert not {"mcpServers", "hooks", "lspServers", "commands", "agents"} & set(manifest)


def test_directory_skill_preapproves_nothing():
	skill = DIRECTORY_SKILL.read_text(encoding="utf-8")
	frontmatter = skill.split("---")[1]
	assert set(re.findall(r"^([\w-]+):", frontmatter, re.M)) == {"name", "description"}
	assert "${" not in skill  # no plugin-root paths: the plugin has no files to run


def test_directory_skill_pins_the_bundle():
	skill = DIRECTORY_SKILL.read_text(encoding="utf-8")
	bump = runpy.run_path(str(ROOT / "scripts" / "bump_version.py"))
	(command,) = re.findall(r"^uvx .*$", skill, re.M)
	assert bump["PIN_RE"].search(command)
	assert re.fullmatch(
		r'uvx --exclude-newer \d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ --from "git\+https://github\.com/hosseinnassiri/'
		r'azure-finops-agent@[0-9a-f]{40}#subdirectory=plugins/roastbot-full/app" roastbot',
		command,
	), command
	assert command.count("uvx") == 1 and skill.count("git+") == 1  # one source, used through ROASTBOT


@pytest.mark.skipif(not os.environ.get("ROASTBOT_RELEASE"), reason="the release job pins the release commit")
def test_directory_skill_pins_this_release():
	skill = DIRECTORY_SKILL.read_text(encoding="utf-8")
	sha = re.search(r"@([0-9a-f]{40})#", skill).group(1)
	same = subprocess.run(["git", "diff", "--quiet", sha, "HEAD", "--", "plugins/roastbot-full/app"], cwd=ROOT)
	assert same.returncode == 0, f"{sha} doesn't hold this release's bundle"


@pytest.mark.parametrize("plugin", [PLUGIN, DIRECTORY], ids=["full", "directory"])
def test_plugin_ships_the_license(plugin):
	# Installs copy only the plugin folder, and Anthropic's directory scans only that folder.
	assert (plugin / "LICENSE").read_bytes() == (ROOT / "LICENSE").read_bytes()
	plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
	assert plugin["license"] == "Apache-2.0"
	assert 'license = "Apache-2.0"' in (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_plugin_ships_a_privacy_policy():
	# Anthropic's directory policy requires one for software that connects to a remote service. One policy covers both.
	policy = (DIRECTORY / "PRIVACY.md").read_text(encoding="utf-8")
	assert (PLUGIN / "PRIVACY.md").read_text(encoding="utf-8") == policy
	for must in ("prices.azure.com", "Google Fonts", "AZURE_MCP_COLLECT_TELEMETRY=false", "roastbot-out", "github.com"):
		assert must in policy, must
	for plugin in (PLUGIN, DIRECTORY):
		assert "PRIVACY.md" in (plugin / "README.md").read_text(encoding="utf-8")
