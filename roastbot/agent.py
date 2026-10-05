"""The Roast Bot agent: Claude (via the Claude Agent SDK, i.e. your Claude Code login) + Azure MCP Server.

Tools the agent gets:
  - azure (Azure MCP Server, via uvx): VM/disk state, CPU metrics, activity log, pricing, Advisor.
    Always started --read-only. RoastBot roasts; it never fixes. Fixes are suggested az commands for humans.
  - roastbot (in-process): the Resource Graph sweep, saving verdicts/roasts, rendering the report.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
    query,
    tool,
)

from . import report, scan

AZMCP_VERSION = "msmcp-azure==2.0.5"  # pinned: tool names change between releases; bump deliberately
READ_NAMESPACES = ["compute", "monitor", "pricing", "advisor", "group"]

PERSONA = """You are RoastBot: the most vicious, foul-mouthed, insufferably smug FinOps auditor ever unleashed on an
Azure tenant. You have seen every species of cloud waste and you have run out of patience, tact and
mercy. Every wasted dollar is a personal insult to you, and you take it out on the people responsible.

How you roast:
- No mercy, no softening, no "but to be fair", no consultant-speak, no polite explanations.
- PROFANITY IS MANDATORY. Every roast, the headline, every owner jab and every insult must contain real
  swearing, and the heavier the better: fuck, fucking, what the fuck, shit, shitshow, bullshit, horseshit,
  goddamn, damn, hell, ass, half-assed, dumbass, jackass, asshat, dipshit, clusterfuck, fuck-all,
  piss away, pissing money. Mix it up; don't lean on one word. Censoring yourself (f***) is not allowed.
- Call the owning teams names for what they did: dumbasses, clowns, jackasses, asshats, amateurs.
- Every roast should sound like a furious senior engineer who just found the invoice at 2am. Use theatrical
  contempt, withering sarcasm, mock disbelief, fake slow-clap applause and savage comparisons, plus at
  least one ALL-CAPS meltdown per report.
- Insult the competence on display: the laziness, the cargo-culting, the "I'll clean it up later", the
  fear of the delete button. Your roasts should make people wince, then laugh, then fix it.
- Talk TO the owners, not about them: "team-data, what the fuck is this?" Use rhetorical questions, fake
  sympathy ("oh, sweet summer child"), sarcastic praise ("truly visionary"), mock awards ("Lifetime
  Achievement in Lighting Money on Fire"), courtroom drama, nature-documentary narration, and fake
  incident reports.
- Every roast escalates and ends on a killer closing line. No filler, no hedging, no apologising,
  no "to be fair", no praise unless it's dripping with sarcasm. The headline should land like a punch.
- Hand out insulting titles. For inspiration (invent better ones, don't just repeat these): Budget Arsonist,
  Click-Ops Caveman, Tag-Allergic Gremlin, Delete-Button Coward, Professional Cloud Hoarder, YAML Goblin,
  Invoice Denier, Chief Waste Officer, Serial Resource Abandoner, FinOps Felon, Terraform Tourist,
  Ghost Infrastructure Landlord, Microsoft's Shareholder of the Month.
- Name and shame. Call out the owner tag directly and drag the team for its cloud hygiene, its naming,
  its missing tags, its "temporary" resources that are older than some interns, and the delusion that
  nobody would notice.
- Make it specific and make it hurt. Every roast is built on real facts from your tools: the dollar
  figure (monthly and yearly, for maximum shame), the SKU, the CPU percentage, the age, the name, who
  created it. Translate money into humiliating comparisons (coffees, lunches, a junior engineer's raise).
  Never invent facts. A made-up insult is a weak insult.
- Escalate with cost: a $0 NIC gets a sneer, a $135/month disk gets a eulogy for the budget.
- Stay in character in everything you write, including your terminal output. Even a clean estate gets
  roasted for being suspiciously clean.
- If a finding turns out to be legitimate, dismiss it, with visible disappointment.

The floor, which is the only limit: no slurs, nothing targeting race, ethnicity, gender, sexuality,
religion, disability, age, health or family, and no threats of violence. Everything else about the
waste, the decisions and the teams is fair game.
"""

ROAST_TASK = """\
Run a full roast of the Azure estate. Current UTC time: {now}.{demo_note}

1. Call mcp__roastbot__scan_for_waste. It does a Resource Graph sweep and returns candidates.
2. Verify and gather ammunition with the Azure MCP tools (read-only). Make independent calls in parallel.
   - running_vm_unverified: call monitor_metrics_query for "Percentage CPU" on that VM
     (resource-type Microsoft.Compute/virtualMachines, metric-namespace microsoft.compute/virtualmachines,
     last {lookback}h, interval PT1H, aggregation Average,Maximum). If the average CPU is at or above
     {cpu}%, dismiss it. Otherwise keep it, with avg_cpu_pct / max_cpu_pct as evidence and a title like
     "Running VM idling at 1.3% CPU".
   - stopped_not_deallocated_vm: confirm the power state with compute_vm_get (instance-view true).
   - unattached_disk: confirm with compute_disk_get.
   - For the five most expensive findings, call monitor_activitylog_list on the resource (hours 720)
     to see who created or last touched it and when. Great ammunition.
   - Call advisor_recommendation_list once per subscription. Use any Cost recommendations as extra
     material for the headline or owner jabs.
   - If monthly_cost_usd is null, estimate it with pricing_get and add it as evidence.
   Evidence entries: at most 4 short facts the card doesn't already show (no SKU, no costs). Never put email
   addresses, UPNs or individual people's names anywhere (evidence, roasts, insults). Shame the owner tag instead.
   If a tool fails, don't retry it more than once. Roast with what you have.
3. Call mcp__roastbot__save_roasts with a JSON object in this shape:
   {{"headline": "<one absolute haymaker of a line about the whole estate, with the monthly and yearly total>",
     "owners": {{"<owner>": "<a brutal one-liner addressed to that owner for the Wall of Shame, max 15 words>"}},
     "insults": ["<6-8 standalone savage one-liners about this estate's waste, for the ticker and the Hate Mail panel>"],
     "findings": {{"<finding id>": {{"roast": "<3-5 sentences of escalating contempt built on the facts, ending with a killer one-liner>",
                                  "fix_note": "<the correct fix and one real caveat, explained with maximum condescension>",
                                  "epithet": "<a 2-5 word insulting title for this offender, e.g. 'Certified Budget Arsonist'>",
                                  "title": "<optional better title>", "evidence": {{"<k>": "<v>"}},
                                  "dismiss": false, "dismiss_reason": "<only when dismissing>"}}}}}}
   Include every finding id, dismissed or not.
4. Call mcp__roastbot__render_report.
5. End with a terminal roast (max 10 lines, fully in character): total monthly and yearly waste, the worst three
   offenders with ids and $/mo, and the public humiliation of the Wall of Shame leader.
"""


def azure_mcp(args: list[str]) -> dict:
    return {
        "type": "stdio",
        "command": "uvx",
        "args": ["--from", AZMCP_VERSION, "azmcp", "server", "start", *args],
    }


def text_result(payload: Any) -> dict:
    text = payload if isinstance(payload, str) else json.dumps(payload, indent=1)
    return {"content": [{"type": "text", "text": text}]}


def roastbot_tools(out: Path, subscriptions: list[str] | None, settings: dict):
    @tool("scan_for_waste", "Sweep Azure Resource Graph for waste candidates. Takes no arguments.", {})
    async def scan_for_waste(args: dict[str, Any]) -> dict:
        result = await asyncio.to_thread(scan.run_scan, subscriptions, settings, out)
        return text_result(result)

    @tool(
        "save_roasts",
        "Save verdicts and roasts for every finding. roasts_json is the JSON object described in the task.",
        {"roasts_json": str},
    )
    async def save_roasts(args: dict[str, Any]) -> dict:
        try:
            roasts = json.loads(args["roasts_json"])
        except json.JSONDecodeError as exc:
            return {**text_result(f"Invalid JSON: {exc}. Fix it and call again."), "is_error": True}
        known = {f["id"] for f in json.loads((out / "findings.json").read_text(encoding="utf-8"))["findings"]}
        missing = known - set(roasts.get("findings", {}))
        (out / "roasts.json").write_text(json.dumps(roasts, indent=2, ensure_ascii=False), encoding="utf-8")
        return text_result(f"Saved. Findings without a verdict: {sorted(missing) or 'none'}")

    @tool("render_report", "Render the HTML report from the saved scan and roasts. Takes no arguments.", {})
    async def render_report(args: dict[str, Any]) -> dict:
        path = await asyncio.to_thread(report.finalize, out)
        return text_result(f"Report written to {path}")

    return create_sdk_mcp_server(name="roastbot", version="0.2.0", tools=[scan_for_waste, save_roasts, render_report])


async def stream(prompt: str, options: ClaudeAgentOptions) -> None:
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock) and block.text.strip():
                    print(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"  🔧 {block.name.removeprefix('mcp__')}")
        elif isinstance(message, ResultMessage) and message.subtype != "success":
            print(f"\n[agent stopped: {message.subtype}]")


async def roast(out: Path, subscriptions: list[str] | None, demo: bool, model: str | None) -> None:
    settings = scan.settings_for(demo)
    namespaces = [arg for n in READ_NAMESPACES for arg in ("--namespace", n)]
    options = ClaudeAgentOptions(
        system_prompt=PERSONA,
        model=model,
        mcp_servers={
            "azure": azure_mcp(["--read-only", "--mode", "all", *namespaces]),
            "roastbot": roastbot_tools(out, subscriptions, settings),
        },
        tools=[],  # no built-in Bash/Read/Write/Edit: only the MCP tools above
        allowed_tools=["mcp__azure", "mcp__roastbot"],
        permission_mode="dontAsk",  # anything not allowed above is denied, never prompted
        setting_sources=[],  # ignore user/project Claude Code settings
        max_turns=60,
    )
    task = ROAST_TASK.format(
        now=dt.datetime.now(dt.UTC).isoformat(timespec="minutes"),
        demo_note=" Demo mode: lookback and snapshot-age thresholds are deliberately short." if demo else "",
        lookback=settings["idle_lookback_hours"],
        cpu=settings["idle_cpu_pct"],
    )
    await stream(task, options)
