import json

from roastbot import report


def scan_of(*findings, at="2026-10-05T00:00:00+00:00"):
	return {"scanned_at": at, "scope": "all", "settings": {}, "findings": list(findings), "errors": []}


def test_dismissed_findings_are_dropped(make_finding):
	scan = scan_of(make_finding("f-1"), make_finding("f-2"))
	kept = report.confirmed(scan, {"findings": {"f-2": {"dismiss": True}}})
	assert [f["id"] for f in kept] == ["f-1"]


def test_verified_running_vm_becomes_idle_vm(make_finding):
	scan = scan_of(make_finding("f-1", detector="running_vm_unverified"))
	kept = report.confirmed(scan, {"findings": {"f-1": {"roast": "lazy", "evidence": {"avg_cpu_pct": 0.4}}}})
	assert kept[0]["detector"] == "idle_vm"
	assert kept[0]["evidence"]["avg_cpu_pct"] == "0.4"


def test_evidence_masks_emails_drops_duplicates_and_caps():
	evidence = {
		"created_by": "someone@contoso.com",
		"sku": "dup",
		"monthly_cost_usd": 1,
		**{f"k{i}": i for i in range(10)},
	}
	tidy = report.tidy_evidence(evidence)
	assert tidy["created_by"] == "[redacted]"
	assert "sku" not in tidy and "monthly_cost_usd" not in tidy
	assert len(tidy) == report.MAX_EVIDENCE


def test_savings_credit_goes_to_owner_of_fixed_finding(tmp_path, make_finding):
	history = tmp_path / "history"
	history.mkdir()
	disk, ip = make_finding("f-disk", cost=135.17), make_finding("f-ip", owner="team-web", cost=3.65)
	(history / "1.json").write_text(json.dumps({"scope": "all", "findings": [disk, ip]}))
	(history / "2.json").write_text(json.dumps({"scope": "all", "findings": [ip]}))
	assert report.savings_leaderboard(history) == {"team-data": 135.17}


def test_savings_ignore_scope_changes(tmp_path, make_finding):
	history = tmp_path / "history"
	history.mkdir()
	(history / "1.json").write_text(json.dumps({"scope": "all", "findings": [make_finding()]}))
	(history / "2.json").write_text(json.dumps({"scope": ["other-sub"], "findings": []}))
	assert report.savings_leaderboard(history) == {}


def test_render_escapes_agent_text(make_finding):
	roasts = {"headline": "<script>alert(1)</script>", "findings": {"f-1": {"roast": "<b>hi</b>"}}}
	html = report.render(scan_of(make_finding()), [make_finding()], roasts, {})
	assert "<script>alert(1)" not in html and "&lt;script&gt;" in html
	assert "<b>hi</b>" not in html


def test_finalize_writes_report_and_history(tmp_path, make_finding):
	(tmp_path / "findings.json").write_text(json.dumps(scan_of(make_finding())))
	path = report.finalize(tmp_path)
	assert path.exists() and "The Daily" in path.read_text(encoding="utf-8")
	assert len(list((tmp_path / "history").glob("*.json"))) == 1


def test_fire_index_and_stamps():
	assert report.fire_index(0) == (0, "Suspiciously clean")
	assert report.fire_index(225.15)[0] == 3
	assert report.stamp_for(135)[0] == "Dumpster fire"
	assert report.stamp_for(0)[0] == "Digital litter"
	assert [report.exhibit(i) for i in (0, 25, 26)] == ["A", "Z", "AA"]


def test_insult_pick_is_stable():
	assert report.pick(report.EPITHETS, "f-1") == report.pick(report.EPITHETS, "f-1")
