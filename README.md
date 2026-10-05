# 🔥 Azure FinOps Roast Bot

A rude, sarcastic AI agent that hunts cloud waste in Azure and publicly humiliates whoever owns it,
with dollar figures, a Wall of Shame and a Savings Heroes leaderboard. It's strictly read-only: it roasts,
it never fixes. Each finding comes with a suggested `az` command for a human to run.

**Stack:** Python · [Claude Agent SDK](https://code.claude.com/docs/en/agent-sdk/python) (runs on your Claude Code login) ·
[Azure MCP Server](https://learn.microsoft.com/azure/developer/azure-mcp-server/) (via `uvx`) · Azure Resource Graph · uv

## How it works

```text
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

No Claude login? See [Running on Microsoft Foundry](#running-on-microsoft-foundry) or
[Using a non-Claude model](#using-a-non-claude-model).

## Use

| Command | What it does |
| --- | --- |
| `uv run roastbot roast` | Full agent run over every subscription you can read |
| `uv run roastbot roast --subscription "Pay-As-You-Go"` | Roast one subscription, by name or ID. Repeat the flag for several. Works with `scan` too. |
| `uv run roastbot roast --guard` | Content-check the roasts with [Jev](https://docs.typesafe.ai/) before they're published (see below) |
| `uv run roastbot roast --demo` | Short thresholds (6 h CPU lookback, any-age snapshots) for freshly planted waste |
| `uv run roastbot scan` | Sweep and report only. No LLM, canned insults. |
| `uv run roastbot report --open` | Re-render the report |
| `uv run roastbot demo plant` / `cleanup` | Plant / remove demo waste in `rg-roastbot-demo` |

Add `--model <id>` before the subcommand to pick a Claude model (default: your Claude Code default).

`--subscription` only sees subscriptions in your current `az` tenant. For one in another tenant, run
`az account set --subscription <id>` first. An unknown or ambiguous name fails fast instead of roasting an empty estate.

### Running on Microsoft Foundry

There are two ways to run RoastBot on a model hosted in [Microsoft Foundry](https://ai.azure.com/):

- **A Claude model** (the default `claude` provider) needs no code changes and no Claude Code login. The Agent SDK
  ships its own Claude Code CLI, and you point it at Foundry with environment variables.
- **A GPT, DeepSeek or other Foundry model** uses `--provider openai`. See [Using a non-Claude model](#using-a-non-claude-model).

For Claude, you need:

- A Foundry resource with a Claude deployment. Pick a fixed model version, not "auto-update".
- The `Azure AI User` or `Cognitive Services User` role on the resource.

Then run:

```powershell
$env:CLAUDE_CODE_USE_FOUNDRY = "1"
$env:ANTHROPIC_FOUNDRY_RESOURCE = "<resource-name>"   # the name alone, not a URL
az login                                             # Foundry auth falls back to DefaultAzureCredential
uv run roastbot --model <deployment-name> roast --demo
```

- **API key instead of `az login`:** set `$env:ANTHROPIC_FOUNDRY_API_KEY` to the key from the resource's
  **Endpoints and keys** page.
- **Always pass `--model`:** without it, Claude Code picks its own default model, which may not be deployed on
  your resource. Foundry doesn't check the model at startup, so the run fails on the first request instead.
- **Set these in your shell:** RoastBot ignores Claude Code's `settings.json` (`setting_sources=[]`), so variables
  set in its `env` block don't reach the agent.

Details: [Claude Code on Microsoft Foundry](https://code.claude.com/docs/en/microsoft-foundry).

### Using a non-Claude model

`--provider openai` runs the same agent (same persona, same read-only Azure MCP tools) on any model behind an
OpenAI-compatible Chat Completions endpoint. It's configured with the `openai` SDK's own environment variables.
Azure OpenAI / Foundry signs in with Entra ID through `az login`, so you don't need a key:

```powershell
uv sync --extra openai
$env:OPENAI_BASE_URL = "https://<resource>.openai.azure.com/openai/v1/"   # needs the Cognitive Services OpenAI User role
az login
uv run roastbot --provider openai --model <deployment-name> roast --demo
```

- **OpenAI:** set `OPENAI_API_KEY`, and leave `OPENAI_BASE_URL` unset.
- **Ollama, LM Studio or vLLM:** set `OPENAI_BASE_URL=http://localhost:11434/v1` and `OPENAI_API_KEY=local`
  (any non-empty value).
- **Default provider:** set `ROASTBOT_PROVIDER=openai` to make it the default.

Tool-calling quality varies by model. Small local models often fumble the multi-step task. If the model stops early,
the report still renders, with house insults in the gaps.

## Development

```powershell
uv sync                                   # includes dev tools (ruff, pytest)
uv run pytest -q                          # unit tests, no Azure needed
uv run ruff check . ; uv run ruff format .
```

VS Code: open the folder and accept the recommended extensions. The interpreter (`.venv`), ruff format-on-save,
pytest discovery and debug configurations (`roast --demo`, `scan --demo`, `report`) are preconfigured. Claude Code:
`.claude/settings.json` pre-approves safe commands and asks before anything destructive, and `.mcp.json` attaches
a read-only Azure MCP server. CI (`.github/workflows/ci.yml`) runs lint, format check and tests.

## Live demo

1. The evening before: `uv run roastbot demo plant` (sandbox subscription, ~$0.30/h). It plants a disk, IPs, NICs,
   a stopped VM, an idle VM and a snapshot. There's no App Service plan, because the demo subscription has no quota for one.
2. Demo: `uv run roastbot roast --demo`. Optional encore: someone runs the suggested `az disk delete ...` for the P30
   disk, then `uv run roastbot scan --demo` (seconds, no LLM). team-data jumps onto Savings Heroes.
3. After: `uv run roastbot demo cleanup`.

## Caveats

- Costs are pay-as-you-go list prices (disks and IPs from an East US table), not invoice amounts.
- The persona is unfiltered: full profanity, owners named and shamed. Its only floor is no slurs, no attacks
  on protected traits (race, gender, religion, disability and so on) and no threats. Check your audience before
  putting it on a big screen. Tune `PERSONA` in `roastbot/agent.py`.
- `--guard` sends every line Claude wrote (which includes resource names and owner tags, but no Azure
  credentials or raw resource data) to TypeSafe AI's Jev, a classifier that scores each line against the
  persona's floor. Flagged lines go back to Claude for a rewrite (up to two rounds), and whatever is still flagged is
  replaced with a house insult. Setup: `uv sync --extra guard` and set `TYPESAFE_API_KEY`. It fails open: with
  no key or with the API down, the report is published with an UNCHECKED banner. Jev is in early access, and
  `THRESHOLD` in `roastbot/guard.py` hasn't been tuned on live roasts yet. TypeSafe says it doesn't train on user data.
- With `--provider openai`, Azure OpenAI's content filter may block the profane persona, and some models refuse it.
  RoastBot stops cleanly and renders what it has. Ask for a deployment with a looser filter, or tone down `PERSONA`.
- Azure MCP is pinned to `msmcp-azure==2.0.5` (`roastbot/agent.py` and `.mcp.json`). Tool names change between releases.

## Roadmap

Teams Adaptive Card output · daily schedule under a Reader managed identity · Cost Management actuals ·
human-approved fixes once Azure MCP has the write tools (VM deallocate, network cleanup).
