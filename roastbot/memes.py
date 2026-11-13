"""Meme cards for the report: a WANTED poster for the worst offender and a tombstone for the budget.

Drawn here as inline SVG, so they need no image service and nothing leaves the machine. The facts on them (names,
dollar figures, owners) come from the findings; only the captions come from the agent (roasts.json "memes"), with
canned fallbacks. Colours are fixed: they're printed objects, the same in light and dark mode.
"""

from __future__ import annotations

import textwrap
from html import escape
from urllib.parse import quote

DISPLAY = "Anton, Impact, 'Arial Narrow Bold', sans-serif"
BODY = "Inter, system-ui, 'Segoe UI', sans-serif"
MONO = "'JetBrains Mono', ui-monospace, Consolas, monospace"

FALLBACK_CHARGES = {
	"unattached_disk": "Billing for storage while attached to absolutely fuck-all",
	"orphaned_public_ip": "Holding a public IP hostage for no goddamn reason",
	"stopped_not_deallocated_vm": "Pretending to be off while billing like it's on, the lying shit",
	"idle_vm": "Running full-time and doing fuck-all",
	"running_vm_unverified": "Running 24/7 and nobody can say why, dammit",
	"empty_app_service_plan": "Renting a whole goddamn plan for zero apps",
	"orphaned_nic": "Squatting on an IP after its VM died, the creepy bastard",
	"old_snapshot": "Hoarding a 'just in case' nobody remembers, for fuck's sake",
}
FALLBACK_LAST_SEEN = "Billing. Always fucking billing."
FALLBACK_EPITAPH = "It could have been a team offsite. Instead it was this shit."


def lines(text: str, width: int, most: int) -> list[str]:
	"""Wrap text for SVG (which can't wrap), ending with an ellipsis if it doesn't fit."""
	wrapped = textwrap.wrap(" ".join(text.split()), width, break_on_hyphens=False) or [""]
	if len(wrapped) > most:
		wrapped = wrapped[:most]
		wrapped[-1] = wrapped[-1][: width - 1].rstrip() + "…"
	return wrapped


def clip(text: str, width: int) -> str:
	return text if len(text) <= width else text[: width - 1] + "…"


def text_block(rows: list[str], x: int, y: int, step: int, **attrs: str) -> str:
	style = " ".join(f'{k.replace("_", "-")}="{v}"' for k, v in attrs.items())
	spans = "".join(f'<tspan x="{x}" dy="{0 if i == 0 else step}">{escape(r)}</tspan>' for i, r in enumerate(rows))
	return f'<text x="{x}" y="{y}" {style}>{spans}</text>'


def svg(body: str, label: str) -> str:
	return (
		f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 300 420" role="img" aria-label="{escape(label)}">'
		f"<title>{escape(label)}</title>{body}</svg>"
	)


def suspect() -> str:
	"""A grumpy server in a mugshot, against a height chart measured in dollars."""
	chart = "".join(
		f'<line x1="70" x2="230" y1="{y}" y2="{y}" stroke="#8a7550" stroke-width="1"/>'
		f'<text x="74" y="{y - 3}" font-family="{MONO}" font-size="8" fill="#8a7550">${amount}</text>'
		for y, amount in ((128, 200), (156, 150), (184, 100), (212, 50))
	)
	server = (
		'<rect x="118" y="128" width="64" height="86" rx="6" fill="#3b342c"/>'
		'<rect x="126" y="170" width="48" height="6" rx="2" fill="#5c5247"/>'
		'<rect x="126" y="182" width="48" height="6" rx="2" fill="#5c5247"/>'
		'<rect x="126" y="194" width="48" height="6" rx="2" fill="#5c5247"/>'
		'<circle cx="168" cy="206" r="2.5" fill="#e8590c"/>'
		'<path d="M134 142 l12 4 M166 142 l-12 4" stroke="#f1e3c2" stroke-width="3" stroke-linecap="round"/>'
		'<circle cx="140" cy="152" r="3" fill="#f1e3c2"/><circle cx="160" cy="152" r="3" fill="#f1e3c2"/>'
		'<path d="M140 164 q10 -6 20 0" stroke="#f1e3c2" stroke-width="2.5" fill="none" stroke-linecap="round"/>'
	)
	frame = '<rect x="66" y="112" width="168" height="112" fill="#e7d4ab" stroke="#3b342c" stroke-width="2"/>'
	return frame + chart + server


def wanted(finding: dict, epithet: str, caption: dict) -> str:
	cost = finding["monthly_cost_usd"] or 0
	charge = caption.get("charge") or FALLBACK_CHARGES.get(finding["detector"], finding["title"])
	last_seen = caption.get("last_seen") or FALLBACK_LAST_SEEN
	ink = "#2a221b"
	body = (
		'<rect width="300" height="420" fill="#f1e3c2"/>'
		'<rect x="8" y="8" width="284" height="404" fill="none" stroke="#2a221b" stroke-width="3"/>'
		'<rect x="13" y="13" width="274" height="394" fill="none" stroke="#2a221b" stroke-width="1"/>'
		f'<text x="150" y="70" text-anchor="middle" font-family="{DISPLAY}" font-size="58" fill="{ink}" '
		'letter-spacing="4">WANTED</text>'
		f'<text x="150" y="96" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{ink}" '
		'letter-spacing="1.5">FOR CRIMES AGAINST THE BUDGET</text>'
		+ suspect()
		+ f'<text x="150" y="248" text-anchor="middle" font-family="{MONO}" font-size="13" font-weight="600" '
		f'fill="{ink}">{escape(clip(finding["resource_name"], 32))}</text>'
		+ f'<text x="150" y="264" text-anchor="middle" font-family="{BODY}" font-size="10.5" font-style="italic" '
		f'fill="#6b5a44">a.k.a. {escape(clip(epithet, 40))}</text>'
		+ text_block(
			lines(f"Charge: {charge}", 42, 3),
			150,
			286,
			14,
			text_anchor="middle",
			font_family=BODY,
			font_size="11.5",
			fill=ink,
		)
		+ text_block(
			lines(f"Last seen: {last_seen}", 46, 2),
			150,
			334,
			13,
			text_anchor="middle",
			font_family=BODY,
			font_size="10.5",
			fill="#6b5a44",
		)
		+ f'<text x="150" y="376" text-anchor="middle" font-family="{DISPLAY}" font-size="24" fill="#c92a2a">'
		f"REWARD: ${cost * 12:,.0f}/YR</text>"
		+ f'<text x="150" y="396" text-anchor="middle" font-family="{MONO}" font-size="9" fill="{ink}">'
		f"in savings · report to {escape(clip(finding['owner'], 28))}</text>"
	)
	return svg(body, f"WANTED: {finding['resource_name']}")


def tombstone(total: float, killer: str, accomplices: int, date: str, caption: dict) -> str:
	epitaph = caption.get("epitaph") or FALLBACK_EPITAPH
	others = f"and {accomplices} accomplice{'s' if accomplices != 1 else ''}" if accomplices else "acting alone"
	stone = "#c9c4b8"
	ink = "#3a3631"
	body = (
		'<rect width="300" height="420" fill="#23212b"/>'
		'<circle cx="244" cy="58" r="22" fill="#efe7d8"/><circle cx="254" cy="52" r="20" fill="#23212b"/>'
		'<g fill="#efe7d8" opacity=".7"><circle cx="40" cy="40" r="1.5"/><circle cx="96" cy="24" r="1"/>'
		'<circle cx="160" cy="48" r="1.2"/><circle cx="200" cy="20" r="1"/><circle cx="70" cy="84" r="1"/></g>'
		f'<path d="M50 372 V150 a100 100 0 0 1 200 0 V372 Z" fill="{stone}" stroke="#9c968a" stroke-width="3"/>'
		'<rect x="0" y="366" width="300" height="54" fill="#2f4a2a"/>'
		'<path d="M30 366 l6 -14 l4 14 M262 366 l5 -18 l5 18 M110 366 l3 -9 l3 9" stroke="#4f7a45" '
		'stroke-width="3" fill="none"/>'
		f'<text x="150" y="128" text-anchor="middle" font-family="{DISPLAY}" font-size="50" fill="{ink}" '
		'letter-spacing="6">R.I.P.</text>'
		f'<text x="150" y="156" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{ink}" '
		'letter-spacing="1.5">HERE LIES</text>'
		f'<text x="150" y="190" text-anchor="middle" font-family="{DISPLAY}" font-size="30" fill="#8f2020">'
		f"${total * 12:,.2f}</text>"
		f'<text x="150" y="208" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{ink}">'
		"OF PERFECTLY GOOD ANNUAL BUDGET</text>"
		f'<text x="150" y="234" text-anchor="middle" font-family="{BODY}" font-size="11" fill="{ink}">'
		f'Killed by <tspan font-weight="700">{escape(clip(killer, 26))}</tspan></text>'
		f'<text x="150" y="250" text-anchor="middle" font-family="{BODY}" font-size="10.5" fill="{ink}">'
		f"{others}</text>"
		+ text_block(
			lines(epitaph, 30, 4),
			150,
			280,
			15,
			text_anchor="middle",
			font_family=BODY,
			font_size="12",
			font_style="italic",
			fill=ink,
		)
		+ f'<text x="150" y="356" text-anchor="middle" font-family="{MONO}" font-size="9" fill="#5e5850">'
		f"Found dead {escape(date)} UTC</text>"
	)
	return svg(body, f"R.I.P. ${total * 12:,.2f} of annual budget")


def download(svg_text: str, name: str) -> str:
	return f'<a download="{name}" href="data:image/svg+xml;charset=utf-8,{quote(svg_text)}">Download SVG</a>'


def section(findings: list[dict], epithets: dict[str, str], captions: dict, killer: str, owners: int, date: str) -> str:
	"""The report's meme section, or "" when there's nothing to roast."""
	if not findings:
		return ""
	worst = max(findings, key=lambda f: f["monthly_cost_usd"] or 0)
	total = sum(f["monthly_cost_usd"] or 0 for f in findings)
	poster = wanted(worst, epithets[worst["id"]], captions.get("wanted") or {})
	grave = tombstone(total, killer, owners - 1, date, captions.get("tombstone") or {})
	cards = "".join(
		f"<figure>{art}<figcaption>{download(art, name)}</figcaption></figure>"
		for art, name in ((poster, "roastbot-wanted.svg"), (grave, "roastbot-tombstone.svg"))
	)
	return (
		'<section class="memes"><h2 class="section-title">Print These Out <small>and tape them to the '
		f'offending team&#39;s fucking door</small></h2><div class="meme-row">{cards}</div></section>'
	)


CSS = """
.memes { margin-bottom:32px; }
.meme-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),340px)); gap:24px; justify-content:center; }
.memes figure { margin:0; text-align:center; }
.memes svg { display:block; width:100%; height:auto; border-radius:4px; box-shadow:0 14px 30px -16px rgba(0,0,0,.5); }
.memes figure:first-child svg { transform:rotate(-1.5deg); }
.memes figure:last-child svg { transform:rotate(1deg); }
.memes figcaption { margin-top:12px; font:500 12px var(--mono); }
.memes figcaption a { color:var(--fire); }
"""
