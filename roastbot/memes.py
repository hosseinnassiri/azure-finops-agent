"""Meme cards for the report: a WANTED poster for the worst offender, an Employee of the Month plaque for the Wall of
Shame leader and a tombstone for the budget.

Drawn here as inline SVG, so they need no image service and nothing leaves the machine. The facts on them (names,
dollar figures, owners) come from the findings; only the captions come from the agent (roasts.json "memes"), with
canned fallbacks. Colours are fixed: they're printed objects, the same in light and dark mode.
"""

from __future__ import annotations

import datetime as dt
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
FALLBACK_CITATION = "Turning a perfectly good cloud budget into a goddamn bonfire"
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


def dumpster_fire() -> str:
	"""The plaque's portrait: the team's finest work."""
	return (
		'<rect x="90" y="98" width="120" height="120" fill="#2b1d14" stroke="url(#rb-gold)" stroke-width="6"/>'
		'<path d="M116 172 C112 152 128 148 124 130 C136 142 140 122 138 108 C152 124 160 134 156 150 '
		'C166 142 170 130 168 120 C182 138 186 156 184 172 Z" fill="#e8590c"/>'
		'<path d="M130 172 C128 158 140 154 138 142 C148 152 152 146 152 136 C162 150 166 160 168 172 Z" fill="#ffc53d"/>'
		'<path d="M108 172 H192 L186 206 H114 Z" fill="#2f6b3a"/>'
		'<rect x="104" y="166" width="92" height="8" rx="2" fill="#24532d"/>'
		'<circle cx="122" cy="208" r="4" fill="#111"/><circle cx="178" cy="208" r="4" fill="#111"/>'
	)


def plaque(owner: str, cost: float, offences: int, date: str, caption: dict) -> str:
	citation = caption.get("citation") or FALLBACK_CITATION
	try:
		month = dt.date.fromisoformat(date).strftime("%B %Y")
	except ValueError:
		month = date
	gold = "#3b2a10"
	screws = "".join(
		f'<circle cx="{x}" cy="{y}" r="4" fill="url(#rb-gold)" stroke="#3b2a10" stroke-width=".8"/>'
		for x, y in ((22, 22), (278, 22), (22, 398), (278, 398))
	)
	body = (
		'<defs><linearGradient id="rb-gold" x1="0" y1="0" x2="1" y2="1">'
		'<stop offset="0" stop-color="#f6d77a"/><stop offset=".5" stop-color="#d4a017"/>'
		'<stop offset="1" stop-color="#a87406"/></linearGradient></defs>'
		'<rect width="300" height="420" rx="12" fill="#6b4428"/>'
		'<rect x="10" y="10" width="280" height="400" rx="8" fill="none" stroke="#4a2e1a" stroke-width="3"/>'
		+ screws
		+ '<rect x="34" y="26" width="232" height="58" rx="4" fill="url(#rb-gold)"/>'
		f'<text x="150" y="52" text-anchor="middle" font-family="{DISPLAY}" font-size="24" fill="{gold}" '
		'letter-spacing="3">EMPLOYEE</text>'
		f'<text x="150" y="75" text-anchor="middle" font-family="{DISPLAY}" font-size="16" fill="{gold}" '
		'letter-spacing="3">OF THE MONTH</text>'
		+ dumpster_fire()
		+ '<rect x="50" y="232" width="200" height="30" rx="3" fill="url(#rb-gold)"/>'
		f'<text x="150" y="252" text-anchor="middle" font-family="{MONO}" font-size="13" font-weight="700" '
		f'fill="{gold}">{escape(clip(owner, 26))}</text>'
		f'<text x="150" y="282" text-anchor="middle" font-family="{MONO}" font-size="10" fill="#f1e3c2" '
		f'letter-spacing="1.5">{escape(month.upper())}</text>'
		f'<text x="150" y="302" text-anchor="middle" font-family="{BODY}" font-size="10" fill="#e7d4ab">'
		"for outstanding achievement in</text>"
		+ text_block(
			lines(citation, 36, 3),
			150,
			320,
			15,
			text_anchor="middle",
			font_family=BODY,
			font_size="12",
			font_style="italic",
			fill="#f1e3c2",
		)
		+ '<rect x="62" y="364" width="176" height="26" rx="3" fill="url(#rb-gold)"/>'
		f'<text x="150" y="381" text-anchor="middle" font-family="{MONO}" font-size="10" font-weight="600" '
		f'fill="{gold}">${cost:,.2f}/mo · {offences} offence{"s" if offences != 1 else ""}</text>'
	)
	return svg(body, f"Employee of the Month: {owner}")


def download(svg_text: str, name: str) -> str:
	return f'<a download="{name}" href="data:image/svg+xml;charset=utf-8,{quote(svg_text)}">Download SVG</a>'


def section(
	findings: list[dict], epithets: dict[str, str], captions: dict, shame: list[tuple[str, float, int]], date: str
) -> str:
	"""The report's meme section, or "" when there's nothing to roast. shame is the Wall of Shame, worst first."""
	if not findings or not shame:
		return ""
	leader, leader_cost, offences = shame[0]
	worst = max(findings, key=lambda f: f["monthly_cost_usd"] or 0)
	total = sum(f["monthly_cost_usd"] or 0 for f in findings)
	poster = wanted(worst, epithets[worst["id"]], captions.get("wanted") or {})
	award = plaque(leader, leader_cost, offences, date, captions.get("plaque") or {})
	grave = tombstone(total, leader, len(shame) - 1, date, captions.get("tombstone") or {})
	cards = "".join(
		f"<figure>{art}<figcaption>{download(art, name)}</figcaption></figure>"
		for art, name in (
			(poster, "roastbot-wanted.svg"),
			(award, "roastbot-employee-of-the-month.svg"),
			(grave, "roastbot-tombstone.svg"),
		)
	)
	return (
		'<section class="memes"><h2 class="section-title">Print These Out <small>and tape them to the '
		f'offending team&#39;s fucking door</small></h2><div class="meme-row">{cards}</div></section>'
	)


CSS = """
.memes { margin-bottom:32px; }
.meme-row { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,240px),330px)); gap:24px; justify-content:center; }
.memes figure { margin:0; text-align:center; }
.memes svg { display:block; width:100%; height:auto; border-radius:4px; box-shadow:0 14px 30px -16px rgba(0,0,0,.5); }
.memes figure:first-child svg { transform:rotate(-1.5deg); }
.memes figure:nth-child(2) svg { transform:rotate(.5deg); }
.memes figure:last-child svg { transform:rotate(1deg); }
.memes figcaption { margin-top:12px; font:500 12px var(--mono); }
.memes figcaption a { color:var(--fire); }
"""
