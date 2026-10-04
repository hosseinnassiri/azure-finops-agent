"""Render out/report.html from out/findings.json + out/roasts.json (the agent's verdicts) + out/history/.

Works without roasts.json too: findings fall back to canned insults.
"""
from __future__ import annotations

import json
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
    for before, after in zip(snapshots, snapshots[1:]):
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


def bar_rows(rows: list[tuple[str, float, str]], css_class: str) -> str:
    top = max((r[1] for r in rows), default=0) or 1
    return "".join(
        f'<li><span class="who">{escape(name)}</span>'
        f'<span class="bar {css_class}"><i style="width:{max(value / top * 100, 2):.1f}%"></i></span>'
        f'<span class="amt">{money(value)}<small>{escape(note)}</small></span></li>'
        for name, value, note in rows
    ) or '<li class="empty">Nobody yet. Fix something and rescan.</li>'


def confirmed(scan: dict, roasts: dict) -> list[dict]:
    """Findings the agent didn't dismiss, with its extra evidence and verdict applied."""
    verdicts = roasts.get("findings", {})
    result = []
    for f in scan["findings"]:
        verdict = verdicts.get(f["id"], {})
        if verdict.get("dismiss"):
            continue
        f = {**f, "evidence": {**f["evidence"], **verdict.get("evidence", {})}}
        if verdict.get("title"):
            f["title"] = verdict["title"]
        if f["detector"] == "running_vm_unverified" and verdict:
            f["detector"] = "idle_vm"
        result.append(f)
    return result


def finding_card(f: dict, roast: dict) -> str:
    evidence = " · ".join(f"{escape(str(k))}: {escape(str(v))}" for k, v in f["evidence"].items())
    fix_note = roast.get("fix_note") or f["fix_summary"]
    return f"""
    <article class="card">
      <header>
        <span class="tag">{escape(f['detector'].replace('_', ' '))}</span>
        <span class="cost">{money(f['monthly_cost_usd'])}<small>/mo</small></span>
      </header>
      <p class="roast">{escape(roast.get('roast') or FALLBACK_ROASTS.get(f['detector'], f['title']))}</p>
      <dl>
        <dt>Resource</dt><dd><b>{escape(f['resource_name'])}</b> in {escape(f['resource_group'])} ({escape(f['location'])})</dd>
        <dt>Owner</dt><dd>{escape(f['owner'])}</dd>
        <dt>SKU</dt><dd>{escape(f['sku'])}</dd>
        <dt>Evidence</dt><dd>{evidence or '—'}</dd>
        <dt>Cost basis</dt><dd>{escape(f['cost_basis'])}</dd>
      </dl>
      <div class="fix">
        <p><b>Fix:</b> {escape(fix_note)}</p>
        <pre><code>{escape(f['fix_command'])}</code></pre>
        <p class="hint">Suggested only. RoastBot never touches your resources; a human runs this.</p>
      </div>
    </article>"""


def render(scan: dict, findings: list[dict], roasts: dict, saved: dict[str, float]) -> str:
    per_finding = roasts.get("findings", {})
    owner_lines = roasts.get("owners", {})
    total = round(sum(f["monthly_cost_usd"] or 0 for f in findings), 2)
    headline = roasts.get("headline") or f"{len(findings)} pieces of cloud waste found."

    shame = [(o, c, f"{n} item{'s' if n != 1 else ''}" + (f" · {owner_lines[o]}" if o in owner_lines else ""))
             for o, c, n in shame_leaderboard(findings)]
    heroes = [(o, c, "/mo saved") for o, c in saved.items()]
    cards = "".join(finding_card(f, per_finding.get(f["id"], {})) for f in findings)
    errors = "".join(f"<li>{escape(e['detector'])}: {escape(e['error'])}</li>" for e in scan.get("errors", []))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>FinOps Roast Report</title>
<style>
:root {{ --bg:#f6f4ef; --panel:#fff; --ink:#1d1b18; --muted:#6b6660; --line:#e4dfd6;
        --hot:#d9480f; --hot-soft:#ffe8d9; --good:#2b8a3e; --good-soft:#e3f5e6; --code:#f1eee8; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#141311; --panel:#1e1c19; --ink:#efebe4; --muted:#a39d94;
        --line:#34302b; --hot:#ff8a4c; --hot-soft:#3a2216; --good:#69db7c; --good-soft:#1b3121; --code:#29261f; }} }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:32px 16px 64px; }}
.hero {{ display:flex; flex-wrap:wrap; gap:24px; align-items:end; justify-content:space-between; margin-bottom:28px; }}
.hero h1 {{ font-size:clamp(26px,4vw,40px); line-height:1.15; margin:6px 0 0; max-width:700px; }}
.eyebrow {{ color:var(--hot); font-weight:700; letter-spacing:.08em; text-transform:uppercase; font-size:12px; }}
.total {{ text-align:right; }}
.total b {{ display:block; font-size:clamp(34px,6vw,56px); color:var(--hot); line-height:1; font-variant-numeric:tabular-nums; }}
.total span {{ color:var(--muted); font-size:13px; }}
.boards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(300px,1fr)); gap:16px; margin-bottom:28px; }}
.panel {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px 20px; }}
.panel h2 {{ margin:0 0 12px; font-size:16px; }}
.panel ol {{ list-style:none; margin:0; padding:0; display:grid; gap:10px; }}
.panel li {{ display:grid; grid-template-columns:minmax(90px,1fr) 2fr auto; gap:10px; align-items:center; }}
.panel li.empty {{ display:block; color:var(--muted); }}
.who {{ font-weight:600; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.bar {{ height:10px; border-radius:99px; overflow:hidden; }}
.bar i {{ display:block; height:100%; border-radius:99px; }}
.bar.hot {{ background:var(--hot-soft); }} .bar.hot i {{ background:var(--hot); }}
.bar.good {{ background:var(--good-soft); }} .bar.good i {{ background:var(--good); }}
.amt {{ font-variant-numeric:tabular-nums; text-align:right; font-weight:600; }}
.amt small {{ display:block; font-weight:400; color:var(--muted); font-size:11px; max-width:220px; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:16px; }}
.card {{ background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:18px 20px; display:flex; flex-direction:column; min-width:0; }}
.card header {{ display:flex; justify-content:space-between; align-items:center; gap:8px; }}
.tag {{ font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); font-weight:600; }}
.cost {{ font-size:22px; font-weight:800; color:var(--hot); font-variant-numeric:tabular-nums; }}
.cost small {{ font-size:12px; color:var(--muted); font-weight:500; }}
.roast {{ font-size:17px; font-weight:600; margin:10px 0 14px; }}
dl {{ display:grid; grid-template-columns:auto 1fr; gap:4px 12px; margin:0 0 14px; font-size:13px; }}
dt {{ color:var(--muted); }} dd {{ margin:0; overflow-wrap:anywhere; }}
.fix {{ margin-top:auto; border-top:1px dashed var(--line); padding-top:12px; font-size:13px; }}
.fix p {{ margin:0 0 8px; }}
pre {{ background:var(--code); border-radius:8px; padding:10px; margin:0 0 8px; overflow-x:auto; font-size:12px; }}
.hint {{ color:var(--muted); }}
.meta {{ color:var(--muted); font-size:12px; margin-top:28px; }}
.errors {{ color:var(--hot); }}
</style></head>
<body><main>
  <section class="hero">
    <div><div class="eyebrow">FinOps Roast Report</div><h1>{escape(headline)}</h1></div>
    <div class="total"><b>{money(total)}</b><span>per month of waste · {money(total * 12)} per year</span></div>
  </section>
  <section class="boards">
    <div class="panel"><h2>🔥 Wall of Shame: current waste by owner</h2><ol>{bar_rows(shame, 'hot')}</ol></div>
    <div class="panel"><h2>🏆 Savings Heroes: waste fixed since earlier scans</h2><ol>{bar_rows(heroes, 'good')}</ol></div>
  </section>
  <section class="cards">{cards or '<p>No waste found. Suspicious, but congratulations.</p>'}</section>
  {f'<ul class="errors">{errors}</ul>' if errors else ''}
  <p class="meta">Scanned {escape(scan['scanned_at'])} · scope: {escape(str(scan['scope']))} ·
    costs are pay-as-you-go list-price estimates, not invoice amounts · generated read-only.</p>
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
