# 🔥 Azure FinOps Roast Bot

A rude, sarcastic AI agent that hunts cloud waste in Azure and publicly humiliates whoever owns it,
with dollar figures, a Wall of Shame and a Savings Heroes leaderboard. It's strictly read-only: it roasts,
it never fixes. Each finding comes with a suggested `az` command for a human to run.

**Stack:** Python · [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/python) (runs on your Claude Code login) ·
[Azure MCP Server](https://learn.microsoft.com/azure/developer/azure-mcp-server/) (via `uvx`) · Azure Resource Graph · uv

## How it works
```
uv run roastbot roast
  └─ Claude (Agent SDK) ── roastbot tools (in-process) ── scan_for_waste: Resource Graph sweep for candidates
                       │                               ├ save_roasts:  verdicts + roasts → out/roasts.json
                       │                               └ render_report → out/report.html (+ history for leaderboard)
                       └─ Azure MCP Server (read-only) ── compute_vm_get / compute_disk_get   confirm state
                                                        ├ monitor_metrics_query               idle-VM CPU check
                                                        ├ monitor_activitylog_list            who made it, when (ammo)
                                                        ├ advisor_recommendation_list         extra material
                                                        └ pricing_get                         missing prices
```
Azure MCP Server has no Resource Graph or networking tools, so the subscription-wide sweep for orphaned
IPs, NICs, empty plans and snapshots is a deterministic Python query. Everything else goes through MCP.

**Detects:** unattached disks · public IPs attached to nothing · VMs stopped but not deallocated ·
idle running VMs (CPU via Azure Monitor) · empty App Service plans · orphaned NICs · old snapshots

## Setup
```powershell
uv sync            # Python deps (Azure MCP is fetched on demand by uvx)
az login           # Azure: used by both the sweep and Azure MCP
claude             # once, if Claude Code isn't logged in yet. The agent reuses that login.
```

## Use
| Command | What it does |
| --- | --- |
| `uv run roastbot roast` | Full agent run over every subscription you can read |
| `uv run roastbot roast --demo` | Short thresholds (6 h CPU lookback, any-age snapshots) for freshly planted waste |
| `uv run roastbot scan` | Sweep and report only. No LLM, canned insults. |
| `uv run roastbot report --open` | Re-render the report |
| `uv run roastbot demo plant` / `cleanup` | Plant / remove demo waste in `rg-roastbot-demo` |

Add `--model <id>` before the subcommand to pick a Claude model (default: your Claude Code default).

## Live demo
1. The evening before: `uv run roastbot demo plant` (sandbox subscription, ~$0.45/h).
2. Demo: `uv run roastbot roast --demo`. Optional encore: someone runs the suggested `az disk delete ...` for the P30
   disk, then `uv run roastbot scan --demo` (seconds, no LLM). team-data jumps onto Savings Heroes.
3. After: `uv run roastbot demo cleanup`.

## Caveats
- Costs are pay-as-you-go list prices (disks and IPs from an East US table), not invoice amounts.
- The persona is unfiltered: full profanity, owners named and shamed. Its only floor is no slurs, no attacks
  on protected traits (race, gender, religion, disability and so on) and no threats. Check your audience before
  putting it on a big screen. Tune `PERSONA` in `roastbot/agent.py`.
- `AZMCP_VERSION` in `roastbot/agent.py` floats to the latest Azure MCP. Pin it before relying on tool names.

## Roadmap
Teams Adaptive Card output · daily schedule under a Reader managed identity · Cost Management actuals ·
human-approved fixes once Azure MCP has the write tools (VM deallocate, network cleanup).
