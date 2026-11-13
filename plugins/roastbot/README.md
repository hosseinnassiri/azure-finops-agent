# RoastBot

A rude, sarcastic Azure FinOps auditor for Claude Code. RoastBot sweeps your Azure subscriptions for cloud waste
(idle and stopped-but-billing VMs, unattached disks, orphaned public IPs and NICs, old snapshots, empty App Service
plans), checks each finding against live Azure data, and writes a savage roast for every one. The result is an
HTML report with dollar figures, a Wall of Shame for the worst-offending teams, a WANTED poster, an Employee of the
Month plaque and a budget tombstone (drawn locally as SVG), and suggested fix commands.

**Claude Code only.** RoastBot needs a local shell, [uv](https://docs.astral.sh/uv/), the
[Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) and an Azure login, so it doesn't work on
claude.ai or in Cowork.

This plugin is instructions only: it contains no code and pre-approves nothing, so Claude Code asks you before every
command it runs. The same skill with its code bundled, a read-only Azure MCP server and the read-only commands
pre-approved is in RoastBot's own marketplace: `/plugin marketplace add hosseinnassiri/azure-finops-agent`, then
`/plugin install roastbot@roastbot`.

## Use

1. Sign in to Azure with `az login` (or run under a managed identity). Reader access is enough.
2. In Claude Code, run `/roastbot:roast`. Add `--subscription <id or name>` to limit the scope, or `--demo` for
   short thresholds that count freshly created waste.
3. Open `roastbot-out/report.html` in the folder you ran it from.

Ask for a "work-safe" roast if you want the contempt without the swearing.

## Examples

- `/roastbot:roast`: roast every subscription you can read.
- `/roastbot:roast --subscription "Production"`: roast one subscription, by name or ID. Repeat the flag for more.
- `Roast our Azure dev subscription, but keep it work-safe`: the same audit and report, without the swearing.
- `Which of my Azure VMs are idle, and what are they costing me?`: Claude picks the skill up from the question.
- `/roastbot:roast --demo`: short thresholds, so resources created in the last few minutes already count as waste.

## Try it without real waste

To see a full roast on a subscription that has nothing to find, clone
<https://github.com/hosseinnassiri/azure-finops-agent>, run `uv run roastbot demo plant` (this creates about $225 a
month of deliberately wasteful resources in a resource group called `rg-roastbot-demo`, using your Azure login), run
`/roastbot:roast --demo`, then remove everything with `uv run roastbot demo cleanup`. The plugin itself contains
none of this demo code.

## Troubleshooting

- **Authentication errors:** run `az login`, then `az account show` to check the account. RoastBot uses the same
  `DefaultAzureCredential` chain as the Azure CLI.
- **"Subscription ... not found or not readable by this identity":** the error lists the subscriptions you can see.
  For another tenant, run `az account set --subscription <id>` first.
- **Zero findings on a subscription you know is messy:** your login may lack Reader access there, or the waste is
  newer than the idle thresholds. Try `--demo`, or pass `--subscription` explicitly.
- **`uv` not found:** install it from <https://docs.astral.sh/uv/getting-started/installation/>, then restart
  Claude Code.
- **The first run is slow:** `uv` downloads RoastBot and the Azure SDK once. Later runs reuse its cache.
- **Permission prompts:** every command asks first. The skill runs only `uvx ... roastbot scan`, `uvx ... roastbot
  report` and the read-only `az` commands it lists (`az monitor metrics list`, `az vm get-instance-view`,
  `az disk show`, `az monitor activity-log list`, `az advisor recommendation list`). Decline anything else.
  Declining a check doesn't stop the roast: RoastBot works with what it has.
- **`az` not found:** install the Azure CLI, run `az login`, then restart Claude Code.

## Support, security and privacy

- Questions and bugs: <https://github.com/hosseinnassiri/azure-finops-agent/issues>
- Security problems: report them privately, as described in
  [SECURITY.md](https://github.com/hosseinnassiri/azure-finops-agent/blob/main/SECURITY.md)
- Privacy policy: [PRIVACY.md](PRIVACY.md), also at
  <https://github.com/hosseinnassiri/azure-finops-agent/blob/main/plugins/roastbot/PRIVACY.md>

## Content warning

By default the roasts are profane and insulting, aimed at the resources and at the teams named in their `owner`
tags. They never name individual people, and they stay away from slurs, protected traits and threats.

## Read-only by design

- RoastBot never creates, changes, deletes, starts or stops anything in Azure. Each finding comes with a suggested
  `az` fix command, which is printed in the report for a person to review and run. The skill tells Claude never
  to run them.
- It's only as read-only as the identity you sign in with, so use a Reader-scoped login where that matters.

## What it runs, reads and sends

- **Runs** RoastBot's read-only scan and report code with
  `uvx --from "git+https://github.com/hosseinnassiri/azure-finops-agent@<commit>#subdirectory=plugins/roastbot-full/app" roastbot ... scan`
  (and `... report`). The commit is fixed in the skill and changes only with a new plugin version. That folder holds
  only the read-only modules: no agent, and none of the repo's demo code that creates and deletes Azure resources.
  `uv` downloads the code from GitHub and its dependencies (the Azure SDK for Python and `requests`) from PyPI into
  its own cache, taking no package published after that release (`--exclude-newer`).
- **Runs read-only `az` commands** to check findings: `az monitor metrics list`, `az vm get-instance-view`,
  `az disk show`, `az monitor activity-log list` and `az advisor recommendation list`. Claude Code asks before each.
- **Uses your Azure login.** The scan authenticates with `DefaultAzureCredential` and the `az` commands with your
  `az login`. Both send that token only to Azure.
- **Reads from Azure**, using your credentials: resource metadata through Azure Resource Graph, CPU metrics,
  activity logs for the most expensive findings, Advisor recommendations and retail prices. Activity logs contain
  the email addresses of the people who changed resources. RoastBot uses them only to see when a resource was
  created or changed, and keeps names and email addresses out of everything it writes.
- **Writes** only to `./roastbot-out/`: `findings.json`, `roasts.json`, `report.html`, a `history/` folder that
  tracks progress between runs, and a cache of public Azure prices.
- **Sends** nothing anywhere else. Its only network traffic is to Azure's APIs, the public Azure retail prices
  API (`prices.azure.com`), and GitHub and PyPI for the downloads. It has no telemetry of its own. The roasts are
  written by the Claude session you're already using.
- **The report** loads its fonts from Google Fonts when you open it in a browser, which is a request to Google.
  It contains nothing else remote.

## License

Apache-2.0. Source, issues and the standalone CLI live at
<https://github.com/hosseinnassiri/azure-finops-agent>.
