# Azure FinOps Roast Bot

Python agent (Claude Agent SDK + Azure MCP Server) that finds Azure waste and roasts the owners, rudely.
It's a contest and demo project, and the first slice of a broader infrastructure-ops agent. See README.md.

## Safety rules (non-negotiable)

- RoastBot never changes Azure. Azure MCP always runs with `--read-only`. Fixes are suggested `az` commands
  shown in the report, for humans to run. There is deliberately no fix command.
- Python code in `roastbot/` never mutates Azure. The Resource Graph sweep is read-only.
- The agent gets no built-in tools (`tools=[]`), `permission_mode="dontAsk"` denies anything not in
  `allowed_tools`, and it ignores Claude Code settings (`setting_sources=[]`).
- The non-Claude engine (`openai_agent.py`, `--provider openai`) can only dispatch the tools it registers: the
  Azure MCP tools (same `azure_mcp_server()`, so always `--read-only`) plus `RoastTools`. Unknown names get an error
  result. Never add a shell, file or write tool to either engine.
- The Claude Code skill (`plugins/roastbot`) can't be sandboxed like that, so its SKILL.md carries the rules in
  prose: never change Azure, never run a finding's `fix_command`, verify only through the plugin's `--read-only`
  Azure MCP server. Keep those rules at the top of the skill.
- In production this runs under a Reader-scoped managed identity (picked up by `DefaultAzureCredential`
  and Azure MCP). Locally it uses `az login`.

## Layout

- `roastbot/agent.py`: persona, task prompt, Agent SDK options, in-process tools
- `roastbot/cli.py`: `roastbot` entry point (roast / scan / report / demo; `--provider claude|openai`)
- `roastbot/detectors.py`: Resource Graph detectors; register new ones in `DETECTORS`
- `roastbot/cloud.py`: Resource Graph paging. `pricing.py`: list-price estimates
- `roastbot/scan.py`: sweep → `out/findings.json`. `report.py`: verdicts + history → `out/report.html`
- `roastbot/demo.py`: plant/cleanup demo waste via `az`
- `roastbot/guard.py`: opt-in (`roast --guard`) Jev content check on the roasts. Fails open. `typesafe-sdk` is the
  optional `guard` extra, imported lazily, so `report.py` only uses the SDK-free `apply`
- `roastbot/openai_agent.py`: the same agent on any OpenAI-compatible endpoint, with our own tool loop. `RoastTools` and
  `ROASTBOT_TOOLS` in `agent.py` are shared by both engines. `openai` is the optional `openai` extra
- `plugins/roastbot/`: the Claude Code plugin (marketplace in `.claude-plugin/marketplace.json`). Its `roast` skill
  has Claude Code play RoastBot: `uvx --from git+...@v<version> roastbot scan`, verify via its own `.mcp.json`, write
  `roasts.json`, `roastbot report`. `tests/test_plugin.py` keeps its persona, MCP server and version in sync with
  `agent.py` and `pyproject.toml`. When you bump the version, bump `plugin.json` and the skill's git tag, and push the tag

## Commands

- Use uv: `uv sync`, `uv run roastbot ...`, `uv add <pkg>`. No pip, no requirements.txt.
- `uv run roastbot scan --demo --no-open` is the quick no-LLM check that the Azure side works.
- Before finishing a change: `uv run ruff check . && uv run ruff format . && uv run pytest -q` (CI runs the same).
- Tests cover logic that needs no Azure (verdicts, redaction, leaderboards, pricing). Don't add tests that hit Azure,
  or TypeSafe: guard tests use a fake client. CI installs all extras (`uv sync --locked --all-extras`).

## Tooling notes
- `.mcp.json` gives Claude Code sessions in this repo the same read-only Azure MCP server the agent uses.
- Azure MCP is pinned (`msmcp-azure==3.0.0`) in `roastbot/agent.py`, `.mcp.json` and `plugins/roastbot/.mcp.json`.
  Bump them together.
- The demo subscription has zero App Service quota, and East US often lacks capacity for small VM sizes.
  `demo plant` defaults to canadacentral and falls back through `VM_SIZES`.
