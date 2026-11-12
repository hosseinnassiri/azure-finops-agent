# RoastBot privacy policy

Effective 12 November 2026. This policy covers both RoastBot Claude Code plugins (the directory's and the one in
RoastBot's own marketplace) and the `roastbot` command-line tool
in <https://github.com/hosseinnassiri/azure-finops-agent>, both maintained by Hossein Nassiri.

## The short version

RoastBot runs entirely on your computer. The developer runs no servers, receives none of your data, and has no
analytics or telemetry. RoastBot reads your Azure resources with your own Azure login and writes its results to a
folder on your machine. You control those files and can delete them at any time.

## What RoastBot reads

Using the Azure identity you're signed in with (`az login` or a managed identity), RoastBot reads:

- **Resource metadata** from Azure Resource Graph: names, IDs, types, SKUs, sizes, regions, tags (including `owner`)
  and power states of virtual machines, disks, public IPs, network interfaces, snapshots and App Service plans.
- **Resource details** that confirm a finding: a VM's power state, a disk's attachment state.
- **CPU metrics** for running virtual machines, from Azure Monitor.
- **Activity logs** for the most expensive findings, from Azure Monitor. These records include the email address
  or user principal name of whoever created or changed a resource.
- **Advisor recommendations** for your subscriptions.
- **Public retail prices** from the Azure retail prices API (`prices.azure.com`), which is unauthenticated.

RoastBot is read-only: it never creates, changes or deletes anything in Azure.

## How it uses that data

Only to find unused or idle resources, estimate what they cost, and write a report with roasts and suggested fixes.
Activity logs are used only to see when a resource was created or last changed. RoastBot is instructed to keep
people's names and email addresses out of everything it writes; it names teams by their `owner` tag instead.

## Where data goes

- **Azure.** Your Azure access token goes only to Azure's APIs, which return your resource data.
- **Claude.** In the plugins, the Claude Code session you're already using reads the scan results and the output of
  the Azure checks (Azure MCP tools, or read-only `az` commands in the directory's plugin) and writes the roasts. That data is handled under your agreement with Anthropic, like anything else in your
  Claude Code session. RoastBot adds no other AI service.
- **Package downloads.** `uv` downloads RoastBot's dependencies and the Azure MCP Server from PyPI, and the
  directory's plugin downloads RoastBot's own code from github.com. These requests carry no Azure data.
- **Google Fonts.** The HTML report loads its fonts from Google Fonts when you open it in a browser, so Google
  receives a standard web request (your IP address and browser details). It receives none of the report's contents.
- **Nowhere else.** The Azure CLI may send its own usage telemetry to Microsoft, under your Azure CLI settings
  (`az config set core.collect_telemetry=false` turns it off). The Azure MCP Server's own usage telemetry to
  Microsoft is turned off (`AZURE_MCP_COLLECT_TELEMETRY=false`).

The standalone command-line tool has three optional modes that send data elsewhere. Each runs only if you
choose it, and the plugins use none of them:

- `roastbot roast` sends the scan results to the Claude model you choose, through the Claude Agent SDK.
- `--provider openai` sends them to the OpenAI-compatible endpoint you configure instead.
- `--guard` sends the generated roast lines, which include resource names and owner tags but no credentials or raw
  Azure data, to TypeSafe AI for a content check.

## What it stores, and for how long

RoastBot writes only to its output folder: `./roastbot-out/` in the plugin, `./out/` by default in the CLI.

- `findings.json`: the resources it flagged, with costs and evidence.
- `roasts.json`: the generated roasts and verdicts.
- `report.html`: the rendered report.
- `history/`: one snapshot per run, so the report can show progress over time.
- `.price-cache.json`: cached public Azure prices.

These files stay on your machine until you delete them. Deleting the folder removes everything RoastBot stored.
The developer never receives a copy.

## Children

RoastBot is a tool for cloud administrators. It isn't intended for anyone under 18, and its default output is
profane.

## Changes

Changes to this policy are published in this file, and the git history shows every revision.

## Contact

For privacy questions, open an issue at <https://github.com/hosseinnassiri/azure-finops-agent/issues>. For a
security concern, report it privately as described in
[SECURITY.md](https://github.com/hosseinnassiri/azure-finops-agent/blob/main/SECURITY.md).
