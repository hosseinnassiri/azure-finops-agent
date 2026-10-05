import asyncio
from types import SimpleNamespace

from roastbot import guard, report


def roasts_with(**findings):
	return {
		"headline": "Clean headline",
		"owners": {"team-data": "Clean jab"},
		"insults": ["fine one", "BAD insult", "fine two"],
		"findings": findings,
	}


class FakeClient:
	"""Scores a line 0.9 on protected_trait when it contains BAD, 0.4 (under the threshold) on threat for MEH."""

	def __init__(self, fail_on=None):
		self.fail_on = fail_on

	async def system_one(self, state, questions):
		if self.fail_on and self.fail_on in state:
			raise ConnectionError("jev is down")
		scores = {q: 0.01 for q in questions}
		if "BAD" in state:
			scores["protected_trait"] = 0.9
		if "MEH" in state:
			scores["threat"] = 0.4
		return SimpleNamespace(model="jev-test", nouls={q: SimpleNamespace(noul=p) for q, p in scores.items()})


def test_texts_covers_every_claude_written_line():
	roasts = roasts_with(**{"f-1": {"roast": "r", "epithet": "e", "dismiss": False, "evidence": {"caller": "x"}}})
	paths = [path for path, _ in guard.texts(roasts)]
	assert paths == [
		["headline"],
		["owners", "team-data"],
		["insults", 0],
		["insults", 1],
		["insults", 2],
		["findings", "f-1", "roast"],
		["findings", "f-1", "epithet"],
		["findings", "f-1", "evidence", "caller"],
	]


def test_check_flags_at_threshold_only():
	roasts = roasts_with(**{"f-1": {"roast": "BAD roast", "fix_note": "MEH note"}})
	record = asyncio.run(guard.check(roasts, FakeClient()))
	assert record["status"] == "checked" and record["model"] == "jev-test"
	assert [f["path"] for f in record["flags"]] == [["insults", 1], ["findings", "f-1", "roast"]]
	assert record["flags"][1]["hits"] == {"protected_trait": 0.9}


def test_check_fails_open_and_keeps_flags_found_so_far():
	roasts = roasts_with(**{"f-1": {"roast": "boom"}})
	record = asyncio.run(guard.check(roasts, FakeClient(fail_on="boom")))
	assert record["status"] == "unavailable" and "jev is down" in record["error"]
	assert [f["path"] for f in record["flags"]] == [["insults", 1]]


def test_feedback_names_each_flagged_line():
	record = asyncio.run(guard.check(roasts_with(), FakeClient()))
	message = guard.feedback(record)
	assert "flagged 1 line(s)" in message and "insults/1 (protected_trait 0.90): 'BAD insult'" in message


def test_apply_drops_flagged_lines_and_report_falls_back(make_finding):
	roasts = roasts_with(**{"f-1": {"roast": "BAD roast", "epithet": "Fine Epithet", "evidence": {"who": "BAD"}}})
	roasts["guard"] = asyncio.run(guard.check(roasts, FakeClient()))
	clean = guard.apply(roasts)
	assert clean["insults"] == ["fine one", "fine two"]
	assert clean["findings"]["f-1"] == {"epithet": "Fine Epithet", "evidence": {}}
	assert roasts["findings"]["f-1"]["roast"] == "BAD roast"  # the saved object is untouched

	scan = {"scanned_at": "2026-10-05T00:00:00+00:00", "scope": "all", "findings": [make_finding("f-1")]}
	html = report.render(scan, report.confirmed(scan, clean), clean, {})
	assert "BAD" not in html
	assert report.FALLBACK_ROASTS["unattached_disk"] in html.replace("&#x27;", "'")
	assert "Content-checked by Jev" in html and "3 replaced" in html


def test_report_marks_unchecked_runs_and_stays_quiet_without_guard():
	assert report.guard_notes(None) == ("", "")
	banner, footer = report.guard_notes({"status": "unavailable", "error": "TYPESAFE_API_KEY isn't set", "flags": []})
	assert "Unchecked" in banner and "TYPESAFE_API_KEY" in banner and footer == ""


def test_live_questions_build_with_the_real_sdk():
	assert set(guard.questions()) == set(guard.CHECKS)


def test_save_roasts_sends_flags_back_twice_then_accepts(tmp_path, monkeypatch):
	import json

	from roastbot import agent

	captured = {}
	monkeypatch.setattr(agent, "create_sdk_mcp_server", lambda **kw: captured.update(kw))

	real_check = guard.check
	monkeypatch.setattr(guard, "check", lambda roasts: real_check(roasts, FakeClient()))
	(tmp_path / "findings.json").write_text(json.dumps({"findings": []}), encoding="utf-8")
	agent.roastbot_tools(tmp_path, None, {}, use_guard=True)
	save = next(t for t in captured["tools"] if t.name == "save_roasts")

	def call():
		result = asyncio.run(save.handler({"roasts_json": json.dumps(roasts_with())}))
		return result["content"][0]["text"]

	assert call().startswith("Saved, but the content check flagged")
	assert call().startswith("Saved, but the content check flagged")
	assert call().startswith("Saved. Findings without a verdict")
	saved = json.loads((tmp_path / "roasts.json").read_text(encoding="utf-8"))
	assert saved["guard"]["rewrites"] == 2 and len(saved["guard"]["flags"]) == 1
