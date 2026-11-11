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
  `agent.py` and `pyproject.toml`

## Releases

- Every push to `main` that changes `plugins/`, `roastbot/`, `.claude-plugin/`, `pyproject.toml` or `uv.lock` is a
  release. The `release` job in `ci.yml` bumps the patch version (`scripts/bump_version.py`), commits
  `Release vX.Y.Z [skip ci]`, tags `vX.Y.Z`, fast-forwards the `release` branch and creates a GitHub release. So
  `git pull` after pushing.
- Don't bump the version by hand for a patch. For a minor or major release, run
  `uv run --no-project python scripts/bump_version.py minor` and push. CI sees the untagged version and releases it as is.
- Never write GitHub's skip-ci marker (square brackets around "skip ci") anywhere in a commit message you push,
  not even quoted: GitHub then runs no workflow for that push, so nothing is checked or released. Only the CI's own
  release commit carries it. If a release was skipped or raced, rerun it with `gh workflow run ci --ref main`.
- Users only receive a plugin change when its `version` changes. The skill's `@vX.Y.Z` pin must name a tag that
  exists, which is why the tag is pushed with the release commit.

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
