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
- The Claude Code skills (both plugins) can't be sandboxed like that, so each SKILL.md carries the rules in
  prose: never change Azure, never run a finding's `fix_command`, verify only through the full plugin's `--read-only`
  Azure MCP server or, in the directory's plugin, only the read-only `az` commands its step 2 lists. Keep those
  rules at the top of each skill.
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
- Two Claude Code plugins, both named `roastbot`, with the same `roast` skill (Claude Code plays RoastBot: scan,
  verify, write `roasts.json`, report). Shared parts (persona, safety rules, steps 3-5, plugin.json, LICENSE,
  PRIVACY.md) must stay identical, and `tests/test_plugin.py` checks that, plus versions, MCP pins and allowed-tools:
  - `plugins/roastbot-full/`: the one in this repo's marketplace (`.claude-plugin/marketplace.json`). Runs the
    bundled `app/` (`uv run --locked --no-editable --isolated --project ${CLAUDE_PLUGIN_ROOT}/app roastbot ... scan`),
    verifies via its own `.mcp.json`, and pre-approves exactly those commands and MCP tools.
  - `plugins/roastbot/`: the Anthropic directory's (portal plugin path, tracking `release`). The directory refuses
    code, local MCP servers and any `allowed-tools` beyond Read/Grep/Glob/LS from non-Verified organizations, so it
    holds only Markdown, JSON, LICENSE and the icon, its frontmatter is just `name` and `description`, and Claude Code
    asks before every command. Its skill runs the full plugin's `app/` with `uvx --exclude-newer <date> --from
    "git+https://github.com/...@<sha>#subdirectory=plugins/roastbot-full/app"` (the release job writes the pin) and
    verifies with read-only `az` commands. Never add a non-doc file or an `allowed-tools` line to it.
  Each `README.md` is that plugin's listing and the security scan's disclosure: when a plugin starts running,
  reading, writing or sending something new, say so there and in `PRIVACY.md` (the policy the directory requires,
  which also covers the CLI's optional data flows). Privately reported security issues come in through `SECURITY.md`
- `plugins/roastbot-full/app/roastbot/` is a generated copy of the read-only modules (`BUNDLE` in
  `scripts/bump_version.py`): never edit it. Change `roastbot/` and the release job copies it over. A bundled module
  must not import `agent`, `demo` or `openai_agent` at module level (`cli.py` imports them inside their commands), and
  must not run subprocesses. When a bundled module needs a new dependency, add it to `plugins/roastbot-full/app/pyproject.toml`
  too, then run `uv lock --project plugins/roastbot-full/app`
- Azure MCP's usage telemetry is off (`AZURE_MCP_COLLECT_TELEMETRY=false` in `azure_mcp()` and both `.mcp.json` files),
  because the plugin README promises no telemetry

## Releases

- Every push to `main` that changes `plugins/`, `roastbot/`, `.claude-plugin/`, `pyproject.toml` or `uv.lock` is a
  release. The `release` job in `ci.yml` bumps the patch version and syncs the plugin's bundle
  (`scripts/bump_version.py`), commits `Release vX.Y.Z [skip ci]`, pins the directory's plugin to that commit in a
  second skip-ci commit (`bump_version.py --pin`), tags `vX.Y.Z`, fast-forwards the `release` branch, creates a GitHub
  release and runs the pinned `uvx` command. So `git pull` after pushing.
- `main` and `release` reject force pushes and deletion, and `v*` tags can't be moved or deleted (repo rulesets).
  Actions in `ci.yml` are pinned to commit SHAs; Dependabot (`.github/dependabot.yml`) proposes updates.
- Don't bump the version by hand for a patch. For a minor or major release, run
  `uv run --no-project python scripts/bump_version.py minor` and push. CI sees the untagged version and releases it as is.
- Never write GitHub's skip-ci marker (square brackets around "skip ci") anywhere in a commit message you push,
  not even quoted: GitHub then runs no workflow for that push, so nothing is checked or released. Only the CI's own
  release commits carry it. If a release was skipped or raced, rerun it with `gh workflow run ci --ref main`.
- Users only receive a plugin change when its `version` changes.

## Commands

- Use uv: `uv sync`, `uv run roastbot ...`, `uv add <pkg>`. No pip, no requirements.txt.
- `uv run roastbot scan --demo --no-open` is the quick no-LLM check that the Azure side works.
- Before finishing a change: `uv run ruff check . && uv run ruff format . && uv run pytest -q` (CI runs the same).
- Tests cover logic that needs no Azure (verdicts, redaction, leaderboards, pricing). Don't add tests that hit Azure,
  or TypeSafe: guard tests use a fake client. CI installs all extras (`uv sync --locked --all-extras`).

## Tooling notes
- `.mcp.json` gives Claude Code sessions in this repo the same read-only Azure MCP server the agent uses.
- Azure MCP is pinned (`msmcp-azure==3.0.0`) in `roastbot/agent.py`, `.mcp.json` and `plugins/roastbot-full/mcp/`
  (`pyproject.toml` plus `uv.lock`: the directory only accepts a lockfile pin, not `uvx pkg==X`). Bump all of them
  together and rerun `uv lock --project plugins/roastbot-full/mcp`; `tests/test_plugin.py` checks they agree.
- The full plugin's `allowed-tools` lists exact MCP tools, never the whole server. The directory's listing icon
  (`plugins/roastbot/.claude-plugin/icon.png`) is fixed the first time the plugin is saved in the portal.
- The demo subscription has zero App Service quota, and East US often lacks capacity for small VM sizes.
  `demo plant` defaults to canadacentral and falls back through `VM_SIZES`.
