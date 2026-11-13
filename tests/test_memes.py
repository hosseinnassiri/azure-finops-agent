"""The WANTED poster and tombstone: facts from the findings, captions from the agent, safe to embed."""

import re
from urllib.parse import unquote
from xml.etree import ElementTree

from roastbot import guard, memes, report
from tests.test_report import scan_of

CAPTIONS = {
	"wanted": {"charge": "Grand theft budget", "last_seen": "rg-temp"},
	"tombstone": {"epitaph": "Gone to Microsoft"},
}


def test_poster_shows_the_most_expensive_finding_and_the_captions(make_finding):
	cheap, worst = make_finding("f-1", cost=3.65), make_finding("f-2", owner="team-web", cost=135.17)
	html = memes.section([cheap, worst], {"f-1": "a", "f-2": "Disk Goblin"}, CAPTIONS, "team-web", 2, "2026-11-13")
	assert "res-f-2" in html and "res-f-1" not in html
	assert "REWARD: $1,622/YR" in html  # yearly, from the findings, not the agent
	assert "Disk Goblin" in html and "Grand theft budget" in html
	assert "$1,665.84" in html  # tombstone: the whole estate's yearly total
	assert "Killed by" in html and "and 1 accomplice" in html and "Gone to Microsoft" in html


def test_cards_fall_back_without_captions(make_finding):
	html = memes.section([make_finding(detector="orphaned_nic")], {"f-1": "x"}, {}, "team-data", 1, "2026-11-13")
	assert memes.FALLBACK_CHARGES["orphaned_nic"][:20] in html
	assert "acting alone" in html


def test_no_findings_no_memes():
	assert memes.section([], {}, CAPTIONS, "", 0, "2026-11-13") == ""


def test_cards_are_valid_svg_with_escaped_text(make_finding):
	evil = make_finding(resource_name="<script>x</script>&")
	captions = {"wanted": {"charge": '"><img src=x onerror=alert(1)>'}}
	html = memes.section([evil], {"f-1": "<b>"}, captions, "o", 1, "d")
	assert "<script>" not in html and "<img" not in html and "<b>" not in html
	for art in re.findall(r"<svg.*?</svg>", html, re.S):
		ElementTree.fromstring(art)  # parses: well-formed, so the download opens too
	for link in re.findall(r'href="data:image/svg\+xml;charset=utf-8,([^"]*)"', html):
		ElementTree.fromstring(unquote(link))


def test_long_captions_wrap_and_stop():
	rows = memes.lines("word " * 60, 30, 3)
	assert len(rows) == 3 and rows[-1].endswith("…") and all(len(r) <= 30 for r in rows)


def test_report_includes_the_cards(make_finding):
	html = report.render(scan_of(make_finding()), [make_finding()], {"memes": CAPTIONS}, {})
	assert "WANTED" in html and "R.I.P." in html and "Grand theft budget" in html


def test_guard_checks_and_drops_meme_captions():
	roasts = {"memes": CAPTIONS}
	paths = [path for path, _ in guard.texts(roasts)]
	assert paths == [["memes", "wanted", "charge"], ["memes", "wanted", "last_seen"], ["memes", "tombstone", "epitaph"]]
	clean = guard.apply({**roasts, "guard": {"flags": [{"path": ["memes", "wanted", "charge"]}]}})
	assert "charge" not in clean["memes"]["wanted"] and clean["memes"]["wanted"]["last_seen"] == "rg-temp"
	assert roasts["memes"]["wanted"]["charge"] == "Grand theft budget"  # apply copies, never mutates
