"""Render out/report.html from out/findings.json + out/roasts.json (the agent's verdicts) + out/history/.

Works without roasts.json too: findings fall back to canned insults.
"""

from __future__ import annotations

import hashlib
import json
import re
import webbrowser
from collections import defaultdict
from html import escape
from pathlib import Path

FALLBACK_ROASTS = {
	"unattached_disk": "A disk attached to NOTHING, billed like it's holding up the whole company. Who signed off on this shit?",
	"orphaned_public_ip": "A public IP pointing at absolutely fuck all. World-class reachability, zero purpose. Just like this team's roadmap.",
	"stopped_not_deallocated_vm": "You 'stopped' it. Azure didn't. Azure is still billing you for the hardware, genius. Read the docs, maybe.",
	"running_vm_unverified": "Running 24/7. Doing what? Nobody knows, nobody checked, nobody cares. The meter cares.",
	"idle_vm": "Sitting at a few percent CPU while you pay for all of it. The most expensive screensaver in the building.",
	"empty_app_service_plan": "A premium App Service plan hosting ZERO apps. You're paying penthouse rent for an empty room. Incredible.",
	"orphaned_nic": "A NIC whose VM died ages ago. It's free, it's useless, and it's squatting on an IP like a ghost that won't leave.",
	"old_snapshot": "A snapshot so old nobody remembers what disaster it was 'just in case' for. Digital hoarding at its finest.",
}


def money(value) -> str:
	return "n/a" if value is None else f"${value:,.2f}"


def savings_leaderboard(history_dir: Path) -> dict[str, float]:
	"""Credit owners for findings that disappeared between consecutive scans of the same scope."""
	snapshots = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(history_dir.glob("*.json"))]
	saved: dict[str, float] = defaultdict(float)
	for before, after in zip(snapshots, snapshots[1:], strict=False):
		if before["scope"] != after["scope"]:
			continue
		remaining = {f["id"] for f in after["findings"]}
		for f in before["findings"]:
			if f["id"] not in remaining:
				saved[f["owner"]] += f["monthly_cost_usd"] or 0
	return dict(sorted(saved.items(), key=lambda kv: kv[1], reverse=True))


def shame_leaderboard(findings: list[dict]) -> list[tuple[str, float, int]]:
	totals: dict[str, list] = defaultdict(lambda: [0.0, 0])
	for f in findings:
		totals[f["owner"]][0] += f["monthly_cost_usd"] or 0
		totals[f["owner"]][1] += 1
	return sorted(((o, round(c, 2), n) for o, (c, n) in totals.items()), key=lambda t: t[1], reverse=True)


EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
SHOWN_ELSEWHERE = {"sku", "monthly_cost_usd", "yearly_cost_usd", "monthly_cost", "yearly_cost", "cost"}
MAX_EVIDENCE = 5


def tidy_evidence(evidence: dict) -> dict:
	"""Drop fields the card already shows, mask email addresses (this goes on a big screen), cap the list."""
	tidy = {}
	for key, value in evidence.items():
		if key.lower() in SHOWN_ELSEWHERE or len(tidy) >= MAX_EVIDENCE:
			continue
		tidy[key] = EMAIL.sub("[redacted]", str(value))
	return tidy


def confirmed(scan: dict, roasts: dict) -> list[dict]:
	"""Findings the agent didn't dismiss, with its extra evidence and verdict applied."""
	verdicts = roasts.get("findings", {})
	result = []
	for f in scan["findings"]:
		verdict = verdicts.get(f["id"], {})
		if verdict.get("dismiss"):
			continue
		f = {**f, "evidence": tidy_evidence({**f["evidence"], **verdict.get("evidence", {})})}
		if verdict.get("title"):
			f["title"] = verdict["title"]
		if f["detector"] == "running_vm_unverified" and verdict:
			f["detector"] = "idle_vm"
		result.append(f)
	return result


FIRE_INDEX = [  # (monthly $ below which, flames, label)
	(0.01, 0, "Suspiciously clean"),
	(25, 1, "Mildly smelly"),
	(100, 2, "Grease fire"),
	(500, 3, "Dumpster fire"),
	(2000, 4, "Tire fire"),
	(float("inf"), 5, "Call the fire department"),
]
EPITHETS = [
	"Certified Budget Arsonist",
	"Click-Ops Dumbass",
	"Tag-Allergic Jackass",
	"Delete-Button Chickenshit",
	"Professional Cloud Hoarder",
	"Half-Assed Architect",
	"Invoice-Ignoring Asshat",
	"Chief Shitshow Officer",
	"Serial Resource Abandoner",
	"Azure's Favourite Dumbass",
	"FinOps Felon",
	"Human Cost Overrun",
	"Distinguished Engineer of Fuck-All",
	"Free-Trial Brain, Enterprise Bill",
	"Terraform Tourist",
	"Microsoft's Shareholder of the Goddamn Month",
	"Ghost Infrastructure Landlord",
	"Portal-Clicking Clown",
]
INSULTS = [
	"Your cloud bill has more red flags than a goddamn Soviet parade.",
	"Somewhere a CFO just felt a disturbance in the force and said 'what the fuck'.",
	"Microsoft thanks you for your generous fucking donation.",
	"This estate isn't architected. It's abandoned, like a shitty Airbnb.",
	"Tagging is free. You still couldn't be bothered, you lazy asshats.",
	"'Temporary' is the most expensive goddamn word in your vocabulary.",
	"Your resources have been running longer than your attention span. Which, granted, isn't hard.",
	"The delete button won't bite, you absolute chickenshits.",
	"Infrastructure as Code? More like Infrastructure as Horseshit.",
	"If pissing money away were a KPI, you'd all be getting promoted.",
	"Your subscription is a museum of dumbass decisions, and admission costs $0.005 an hour.",
	"Cost optimization called. It wants to know what the fuck you're doing.",
	"Every orphaned resource here is some jackass's 'I'll clean it up on Friday'.",
	"Even Azure Advisor gave up on you and started recommending therapy.",
]
STAMPS = [
	(100, "Dumpster fire", "hot"),
	(25, "Certified garbage", "warm"),
	(1, "Petty larceny", "mild"),
	(0, "Digital litter", "mild"),
]


def plural(n: int, word: str) -> str:
	return f"{n} {word}{'s' if n != 1 else ''}"


def fire_index(total: float) -> tuple[int, str]:
	return next((flames, label) for limit, flames, label in FIRE_INDEX if total < limit)


def stamp_for(cost: float | None) -> tuple[str, str]:
	return next((label, tone) for floor, label, tone in STAMPS if (cost or 0) >= floor)


def exhibit(n: int) -> str:
	letters = ""
	n += 1
	while n:
		n, r = divmod(n - 1, 26)
		letters = chr(65 + r) + letters
	return letters


def board(rows: list[tuple[str, float, str]], tone: str, empty: str) -> str:
	if not rows:
		return f'<p class="empty">{empty}</p>'
	top = max(r[1] for r in rows) or 1
	items = []
	for rank, (name, value, note) in enumerate(rows, 1):
		crown = "🤡" if rank == 1 else f"#{rank}"
		items.append(
			f'<li><span class="rank">{crown}</span><div class="who"><b>{escape(name)}</b>'
			f'<small>{escape(note)}</small></div><span class="amt">{money(value)}<em>/mo</em></span>'
			f'<span class="bar {tone}"><i style="width:{max(value / top * 100, 3):.1f}%"></i></span></li>'
		)
	return f'<ol class="board">{"".join(items)}</ol>'


def pick(options: list[str], key: str) -> str:
	"""Stable choice per key, so a finding keeps its insult across re-renders."""
	return options[int(hashlib.sha1(key.encode()).hexdigest(), 16) % len(options)]


def finding_card(n: int, f: dict, roast: dict) -> str:
	cost = f["monthly_cost_usd"]
	epithet = roast.get("epithet") or pick(EPITHETS, f["id"])
	label, tone = stamp_for(cost)
	evidence = "".join(
		f"<li><span>{escape(str(k).replace('_', ' '))}</span><b>{escape(str(v))}</b></li>"
		for k, v in f["evidence"].items()
	)
	fix_note = roast.get("fix_note") or f["fix_summary"]
	yearly = money(cost * 12) if cost is not None else "n/a"
	return f"""
    <article class="card">
      <div class="stamp {tone}">{escape(label)}</div>
      <header><span class="exhibit">Exhibit {exhibit(n)}</span><span class="kind">{escape(f["title"])}</span></header>
      <h3>{escape(f["resource_name"])}</h3>
      <p class="where">{escape(f["resource_group"])} · {escape(f["location"])} · owned by <b>{escape(f["owner"])}</b></p>
      <blockquote>{escape(roast.get("roast") or FALLBACK_ROASTS.get(f["detector"], f["title"]))}</blockquote>
      <p class="verdict">Verdict: <b>{escape(f["owner"])}</b>, {escape(epithet)}</p>
      <div class="receipt">
        <div class="line"><span>SKU</span><b>{escape(f["sku"])}</b></div>
        {f'<ul class="evidence">{evidence}</ul>' if evidence else ""}
        <div class="line total"><span>Monthly damage</span><b>{money(cost)}</b></div>
        <div class="line"><span>Yearly damage</span><b>{yearly}</b></div>
        <p class="basis">{escape(f["cost_basis"])}</p>
      </div>
      <details>
        <summary>How to stop embarrassing yourself (it's one fucking command, champ)</summary>
        <p>{escape(fix_note)}</p>
        <pre><code>{escape(f["fix_command"])}</code></pre>
        <p class="hint">Suggested only. RoastBot judges; it doesn't clean up after you. That part is your goddamn job, champ.</p>
      </details>
    </article>"""


CSS = """
:root {
  --bg:#f2ede3; --panel:#fffdf8; --ink:#17130f; --muted:#6d665c; --line:#ddd4c4; --code:#efe7d8;
  --fire:#e8590c; --fire-2:#c92a2a; --gold:#b07a00; --good:#2b8a3e; --good-soft:#dcf2e0; --hot-soft:#fde4d3;
  --ticker-bg:#17130f; --ticker-ink:#f2ede3; --ticker-accent:#ffc53d;
  --display:"Anton","Impact","Arial Narrow Bold",sans-serif; --body:"Inter",system-ui,-apple-system,"Segoe UI",sans-serif;
  --mono:"JetBrains Mono",ui-monospace,Consolas,monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#110d0a; --panel:#1b1511; --ink:#f4ede3; --muted:#a6998a; --line:#382c23; --code:#261d16;
  --fire:#ff7a2f; --fire-2:#ff5c5c; --gold:#ffc53d; --good:#69db7c; --good-soft:#163020; --hot-soft:#3b1f12;
  --ticker-bg:#2a1f17; --ticker-ink:#f4ede3; --ticker-accent:#ffc53d; } }
:root[data-theme="dark"] {
  --bg:#110d0a; --panel:#1b1511; --ink:#f4ede3; --muted:#a6998a; --line:#382c23; --code:#261d16;
  --fire:#ff7a2f; --fire-2:#ff5c5c; --gold:#ffc53d; --good:#69db7c; --good-soft:#163020; --hot-soft:#3b1f12;
  --ticker-bg:#2a1f17; --ticker-ink:#f4ede3; --ticker-accent:#ffc53d; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.55 var(--body);
  background-image:radial-gradient(1200px 380px at 50% -200px, color-mix(in srgb, var(--fire) 22%, transparent), transparent); }
main { max-width:1120px; margin:0 auto; padding:28px 16px 64px; }

.masthead { display:flex; flex-wrap:wrap; gap:16px 24px; align-items:center; justify-content:space-between;
  border-bottom:3px double var(--ink); padding-bottom:14px; }
.logo { font:400 clamp(30px,5vw,46px)/1 var(--display); letter-spacing:.04em; text-transform:uppercase; margin:0; }
.logo span { color:var(--fire); }
.dateline { font:500 12px/1.4 var(--mono); color:var(--muted); text-transform:uppercase; letter-spacing:.06em; margin-top:6px; overflow-wrap:anywhere; }
.index { text-align:right; }
.index small { display:block; font:600 11px var(--mono); letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
.index .flames i { font-style:normal; font-size:22px; filter:grayscale(1) opacity(.25); }
.index .flames i.on { filter:none; }
.index b { display:block; font:400 20px/1.1 var(--display); text-transform:uppercase; letter-spacing:.04em; color:var(--fire-2); }

.headline { margin:22px 0 18px; padding:2px 0 2px 16px; border-left:5px solid var(--fire); }
.headline p { margin:0; font:600 clamp(16px,2vw,20px)/1.45 var(--body); max-width:880px; }
.headline cite { display:block; margin-top:6px; font:500 12px var(--mono); color:var(--muted); font-style:normal; }

.ticker { overflow:hidden; background:var(--ticker-bg); color:var(--ticker-ink); border-radius:6px; margin-bottom:20px; }
.track { display:inline-flex; gap:40px; padding:9px 0; white-space:nowrap; animation:scroll 40s linear infinite; font:500 13px var(--mono); }
.track span::before { content:"🔥 "; }
.track b { color:var(--ticker-accent); text-transform:uppercase; }
@keyframes scroll { from { transform:translateX(0) } to { transform:translateX(-50%) } }
@media (prefers-reduced-motion: reduce) { .track { animation:none; white-space:normal; flex-wrap:wrap; padding:9px 14px; gap:8px 24px; } }

.stats { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,200px),1fr)); gap:12px; margin-bottom:24px; }
.stat { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:14px 16px; }
.stat small { display:block; font:600 11px var(--mono); letter-spacing:.1em; text-transform:uppercase; color:var(--muted); }
.stat b { display:block; font:400 clamp(28px,4vw,38px)/1.1 var(--display); color:var(--fire); font-variant-numeric:tabular-nums; margin-top:4px; }
.stat span { font-size:12px; color:var(--muted); }

.boards { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr)); gap:16px; margin-bottom:32px; }
.panel { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px 20px; }
.panel h2 { margin:0 0 4px; font:400 22px/1.1 var(--display); text-transform:uppercase; letter-spacing:.03em; }
.panel .sub { margin:0 0 14px; color:var(--muted); font-size:13px; }
.board { list-style:none; margin:0; padding:0; display:grid; gap:14px; }
.board li { display:grid; grid-template-columns:34px 1fr auto; gap:2px 10px; align-items:center; }
.rank { grid-row:span 2; font:600 15px var(--mono); color:var(--muted); text-align:center; }
.who { min-width:0; } .who b { display:block; }
.who small { display:block; color:var(--muted); font-size:12px; overflow-wrap:anywhere; }
.amt { font:600 15px var(--mono); text-align:right; } .amt em { font-style:normal; color:var(--muted); font-size:11px; }
.bar { grid-column:2 / 4; height:8px; border-radius:99px; overflow:hidden; }
.bar i { display:block; height:100%; border-radius:99px; }
.bar.hot { background:var(--hot-soft); } .bar.hot i { background:linear-gradient(90deg,var(--gold),var(--fire),var(--fire-2)); }
.bar.good { background:var(--good-soft); } .bar.good i { background:var(--good); }
.empty { color:var(--muted); margin:0; }

.section-title { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 12px; margin:0 0 14px; font:400 28px/1 var(--display); text-transform:uppercase; letter-spacing:.03em; }
.section-title small { font:500 12px var(--mono); color:var(--muted); letter-spacing:.06em; }
.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(min(100%,330px),1fr)); gap:18px; }
.card { position:relative; background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px 20px 16px;
  display:flex; flex-direction:column; min-width:0; overflow:hidden; box-shadow:0 10px 30px -18px rgba(0,0,0,.35); }
.card header { display:flex; flex-direction:column; gap:2px; padding-right:120px; }
.exhibit { font:600 11px var(--mono); letter-spacing:.14em; text-transform:uppercase; color:var(--fire); }
.kind { font-size:12px; color:var(--muted); }
.card h3 { margin:8px 0 2px; font:600 16px/1.3 var(--mono); overflow-wrap:anywhere; }
.where { margin:0 0 12px; font-size:12px; color:var(--muted); } .where b { color:var(--ink); white-space:nowrap; }
.stamp { position:absolute; top:16px; right:-4px; transform:rotate(8deg); padding:4px 12px; border:3px solid currentColor; border-radius:6px;
  font:400 15px/1 var(--display); letter-spacing:.06em; text-transform:uppercase; background:var(--panel); }
.stamp.hot { color:var(--fire-2); } .stamp.warm { color:var(--fire); } .stamp.mild { color:var(--gold); }
blockquote { margin:0 0 14px; font-size:15.5px; font-weight:500; line-height:1.55; }
blockquote::before { content:"\\201C"; font:400 44px/0 var(--display); color:var(--fire); vertical-align:-18px; margin-right:4px; }
.receipt { font:12.5px/1.5 var(--mono); background:var(--code); border-radius:8px; padding:10px 12px; margin-bottom:12px; }
.receipt .line { display:flex; justify-content:space-between; gap:12px; }
.receipt .line b { font-weight:600; text-align:right; overflow-wrap:anywhere; }
.receipt .total { border-top:1px dashed var(--muted); margin-top:6px; padding-top:6px; color:var(--fire-2); font-size:14px; }
.evidence { list-style:none; margin:4px 0 0; padding:0; }
.evidence li { display:flex; justify-content:space-between; gap:12px; color:var(--muted); }
.evidence li b { color:var(--ink); font-weight:500; text-align:right; overflow-wrap:anywhere; }
.basis { margin:6px 0 0; color:var(--muted); font-size:11px; }
details { margin-top:auto; border-top:1px dashed var(--line); padding-top:10px; font-size:13px; }
summary { cursor:pointer; font-weight:600; color:var(--fire); }
details p { margin:8px 0; }
pre { background:var(--code); border-radius:8px; padding:10px; margin:0 0 6px; overflow-x:auto; font:12px var(--mono); }
.hint { color:var(--muted); font-size:12px; }
.verdict { margin:-4px 0 14px; font:500 12px var(--mono); color:var(--muted); text-transform:uppercase; letter-spacing:.04em; }
.verdict b { color:var(--fire-2); }
.hate { margin-bottom:32px; }
.hate ul { margin:0; padding:0; list-style:none; display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr)); gap:10px 24px; }
.hate li { font-weight:600; padding-left:26px; position:relative; }
.hate li::before { content:"🖕"; position:absolute; left:0; }
.clean { background:var(--panel); border:1px dashed var(--line); border-radius:14px; padding:28px; text-align:center; color:var(--muted); }
.errors { color:var(--fire-2); font:12px var(--mono); }
footer { margin-top:36px; padding-top:14px; border-top:3px double var(--ink); color:var(--muted); font:12px/1.6 var(--mono); }
"""

FONTS = (
	'<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
	'<link href="https://fonts.googleapis.com/css2?family=Anton&family=Inter:wght@400;500;600;800'
	'&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">'
)


def render(scan: dict, findings: list[dict], roasts: dict, saved: dict[str, float]) -> str:
	per_finding = roasts.get("findings", {})
	owner_lines = roasts.get("owners", {})
	total = round(sum(f["monthly_cost_usd"] or 0 for f in findings), 2)
	headline = (
		roasts.get("headline")
		or f"{len(findings)} pieces of cloud waste found. Nobody is surprised. Everybody should be ashamed."
	)
	flames, severity = fire_index(total)
	shame_rows = shame_leaderboard(findings)
	owners = len(shame_rows)

	shame = [
		(o, c, plural(n, "offence") + (f" · {owner_lines[o]}" if o in owner_lines else "")) for o, c, n in shame_rows
	]
	heroes = [(o, c, "saved. Finally. Took you long enough.") for o, c in saved.items()]
	cards = "".join(finding_card(i, f, per_finding.get(f["id"], {})) for i, f in enumerate(findings))
	errors = "".join(f"<li>{escape(e['detector'])}: {escape(e['error'])}</li>" for e in scan.get("errors", []))
	bonus = roasts.get("insults", [])
	jabs = [f"<span><b>{escape(o)}</b> {escape(line)}</span>" for o, line in owner_lines.items()]
	canned = [f"<span>{escape(i)}</span>" for i in (bonus or INSULTS)]
	mixed = [item for pair in zip(canned, jabs + canned, strict=False) for item in pair] if jabs else canned
	ticker = f'<div class="ticker"><div class="track">{"".join(mixed * 2)}</div></div>'
	hate_mail = "".join(
		f"<li>{escape(i)}</li>" for i in (bonus or [pick(INSULTS, scan["scanned_at"] + str(k)) for k in range(4)])
	)
	scanned = scan["scanned_at"].replace("T", " ").split("+")[0]
	flame_icons = "".join(f'<i class="{"on" if i < flames else ""}">🔥</i>' for i in range(5))
	clean = (
		'<div class="clean">No waste found. Either you are a FinOps saint or the scan is lying. '
		"Statistically, the scan is lying.</div>"
	)

	return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Daily Burn</title>
{FONTS}
<style>{CSS}</style></head>
<body><main>
  <header class="masthead">
    <div>
      <h1 class="logo">The Daily <span>Burn</span></h1>
      <div class="dateline">Your cloud bill's worst fucking nightmare · Read it and weep · {escape(scanned)} UTC · {escape(str(scan.get("scope_label", scan["scope"])))}</div>
    </div>
    <div class="index"><small>Dumpster Fire Index</small><div class="flames">{flame_icons}</div><b>{severity}</b></div>
  </header>

  <section class="headline"><p>{escape(headline)}</p><cite>RoastBot, who has seen your invoice and needs a fucking drink</cite></section>
  {ticker}

  <section class="stats">
    <div class="stat"><small>Monthly burn</small><b>{money(total)}</b><span>pissed away every month, apparently on purpose</span></div>
    <div class="stat"><small>Yearly burn</small><b>{money(total * 12)}</b><span>if nobody lifts a goddamn finger (spoiler: they won't)</span></div>
    <div class="stat"><small>Offences</small><b>{len(findings)}</b><span>across {plural(owners, "owner")} who should know better, for fuck's sake</span></div>
    <div class="stat"><small>In coffees</small><b>☕ {total / 5:,.0f}</b><span>per month you could've drunk instead of setting shit on fire</span></div>
  </section>

  <section class="boards">
    <div class="panel"><h2>🔥 Wall of Shame</h2><p class="sub">Ranked by how much money they lit on fire. Let's give these dumbasses a hand. 👏 Slowly.</p>
      {board(shame, "hot", "Nobody. Which is suspicious as hell.")}</div>
    <div class="panel"><h2>🏆 Savings Heroes</h2><p class="sub">People who actually fixed their shit. Rarer than a quiet on-call week.</p>
      {board(heroes, "good", "🦗 Crickets. Not one of you has fixed a single goddamn thing. Shocking. Truly.")}</div>
  </section>

  <section class="panel hate"><h2>💌 Hate Mail</h2><p class="sub">Unsolicited feedback, delivered with love. Just kidding, fuck your feelings.</p>
    <ul>{hate_mail}</ul></section>

  <h2 class="section-title">The Evidence <small>{plural(len(findings), "exhibit")} of half-assed negligence, worst first</small></h2>
  <section class="cards">{cards or clean}</section>
  {f'<ul class="errors">{errors}</ul>' if errors else ""}

  <footer>Prices are pay-as-you-go list estimates, not invoice amounts. Your dignity was not priced; it was already worth jack shit.
    Generated read-only: RoastBot judges, it doesn't clean up your mess. Complaints go to /dev/null.</footer>
</main></body></html>"""


def finalize(out: Path, open_browser: bool = False) -> Path:
	"""Apply the agent's verdicts, record a history snapshot for the leaderboard, and render the report."""
	scan = json.loads((out / "findings.json").read_text(encoding="utf-8"))
	roasts_file = out / "roasts.json"
	# Verdicts are keyed by stable finding id, so they carry over to rescans (e.g. after someone fixes something).
	roasts = json.loads(roasts_file.read_text(encoding="utf-8")) if roasts_file.exists() else {}
	findings = confirmed(scan, roasts)

	history = out / "history"
	history.mkdir(parents=True, exist_ok=True)
	stamp = scan["scanned_at"].replace(":", "").replace("-", "").replace("+0000", "Z")
	snapshot = {"scanned_at": scan["scanned_at"], "scope": scan["scope"], "findings": findings}
	(history / f"{stamp}.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

	report = out / "report.html"
	report.write_text(render(scan, findings, roasts, savings_leaderboard(history)), encoding="utf-8")
	if open_browser:
		webbrowser.open(report.resolve().as_uri())
	return report.resolve()
