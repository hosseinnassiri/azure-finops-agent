# RoastBot

A rude, sarcastic Azure FinOps auditor for Claude Code. RoastBot sweeps your Azure subscriptions for cloud waste
(idle and stopped-but-billing VMs, unattached disks, orphaned public IPs and NICs, old snapshots, empty App Service
plans), checks each finding against live Azure data, and writes a savage roast for every one. The result is an
HTML report with dollar figures, a Wall of Shame for the worst-offending teams and suggested fix commands.

**Claude Code only.** RoastBot needs a local shell, [uv](https://docs.astral.sh/uv/) and an Azure login, so it
doesn't work on claude.ai or in Cowork.

## Use

1. Sign in to Azure with `az login` (or run under a managed identity). Reader access is enough.
2. In Claude Code, run `/roastbot:roast`. Add `--subscription <id or name>` to limit the scope, or `--demo` for
   short thresholds that count freshly created waste.
3. Open `roastbot-out/report.html` in the folder you ran it from.

Ask for a "work-safe" roast if you want the contempt without the swearing.

## Content warning

By default the roasts are profane and insulting, aimed at the resources and at the teams named in their `owner`
tags. They never name individual people, and they stay away from slurs, protected traits and threats.

## Read-only by design

- RoastBot never creates, changes, deletes, starts or stops anything in Azure. Each finding comes with a suggested
  `az` fix command, which is printed in the report for a person to review and run. The skill tells Claude never
  to run them.
- It's only as read-only as the identity you sign in with, so use a Reader-scoped login where that matters.

## What it runs, reads and sends

- **Runs** the scan and report code bundled in this plugin's `app/` folder, with
  `uv run --locked --no-editable --isolated --project <plugin>/app roastbot ... scan` (and `... report`). The bundle
  holds only the read-only modules: no agent, and none of the repo's demo code that creates and deletes Azure
  resources. `uv` installs its dependencies (the Azure SDK for Python and `requests`) from PyPI, pinned by
  `app/uv.lock`, into a throwaway environment, so nothing is written into the plugin folder. The skill pre-approves
  exactly those two commands.
- **Starts** the Azure MCP Server (`msmcp-azure` 3.0.0 from PyPI, pinned by hash in `mcp/uv.lock`) with
  `uv run --locked --isolated --project <plugin>/mcp azmcp server start --read-only`, limited to its compute,
  monitor, pricing, advisor and group tools, with its usage telemetry to Microsoft turned off
  (`AZURE_MCP_COLLECT_TELEMETRY=false`). The skill pre-approves exactly the six read-only tools it calls:
  `monitor_metrics_query`, `compute_vm_get`, `compute_disk_get`, `monitor_activitylog_list`,
  `advisor_recommendation_list` and `pricing_get`.
- **Uses your Azure login.** The bundled scan and the Azure MCP Server both authenticate with
  `DefaultAzureCredential` (your `az login` or a managed identity) and send that token only to Azure.
- **Reads from Azure**, using your credentials: resource metadata through Azure Resource Graph, CPU metrics,
  activity logs for the most expensive findings, Advisor recommendations and retail prices. Activity logs contain
  the email addresses of the people who changed resources. RoastBot uses them only to see when a resource was
  created or changed, and keeps names and email addresses out of everything it writes.
- **Writes** only to `./roastbot-out/`: `findings.json`, `roasts.json`, `report.html` and a `history/` folder that
  tracks progress between runs. The skill pre-approves reading and writing in that folder and nowhere else.
- **Sends** nothing anywhere else. Its only network traffic is to Azure's APIs, the public Azure retail prices
  API (`prices.azure.com`) and PyPI for the dependency downloads. It has no telemetry of its own. The roasts are
  written by the Claude session you're already using.
- **The report** loads its fonts from Google Fonts when you open it in a browser, which is a request to Google.
  It contains nothing else remote.

## License

Apache-2.0. Source, issues and the standalone CLI live at
<https://github.com/hosseinnassiri/azure-finops-agent>.
