# Azure FinOps Roast Bot

Python agent (Claude Agent SDK + Azure MCP Server) that finds Azure waste and roasts the owners, rudely.
It's a contest and demo project, and the first slice of a broader infrastructure-ops agent. See README.md.

## Safety rules (non-negotiable)

- RoastBot never changes Azure. Azure MCP always runs with `--read-only`. Fixes are suggested `az` commands
  shown in the report, for humans to run. There is deliberately no fix command.
- Python code in `roastbot/` never mutates Azure. The Resource Graph sweep is read-only.
- The agent gets no built-in tools (`tools=[]`), `permission_mode="dontAsk"` denies anything not in
  `allowed_tools`, and it ignores Claude Code settings (`setting_sources=[]`).
- In production this runs under a Reader-scoped managed identity (picked up by `DefaultAzureCredential`
  and Azure MCP). Locally it uses `az login`.

## Layout

- `roastbot/agent.py`: persona, task prompt, Agent SDK options, in-process tools
- `roastbot/cli.py`: `roastbot` entry point (roast / scan / report / demo)
- `roastbot/detectors.py`: Resource Graph detectors; register new ones in `DETECTORS`
- `roastbot/cloud.py`: Resource Graph paging. `pricing.py`: list-price estimates
- `roastbot/scan.py`: sweep → `out/findings.json`. `report.py`: verdicts + history → `out/report.html`
- `roastbot/demo.py`: plant/cleanup demo waste via `az`

## Commands

- Use uv: `uv sync`, `uv run roastbot ...`, `uv add <pkg>`. No pip, no requirements.txt.
- `uv run roastbot scan --demo --no-open` is the quick no-LLM check that the Azure side works.
