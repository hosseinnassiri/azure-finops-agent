"""Deterministic Resource Graph sweep -> out/findings.json. No LLM involved."""

from __future__ import annotations

import datetime as dt
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .detectors import DETECTORS

DEFAULTS = {"idle_lookback_hours": 168, "idle_cpu_pct": 5.0, "snapshot_age_days": 30}
DEMO = {"idle_lookback_hours": 6, "idle_cpu_pct": 10.0, "snapshot_age_days": 0}


def settings_for(demo: bool) -> dict:
	return dict(DEMO if demo else DEFAULTS)


def scope_label(subscriptions: list[dict] | None) -> str:
	if not subscriptions:
		return "all accessible subscriptions"
	return ", ".join(s["name"] for s in subscriptions)


def run_scan(subscriptions: list[dict] | None, settings: dict, out: Path) -> dict:
	"""subscriptions: resolved [{"id", "name"}] from cloud.resolve_subscriptions, or None for everything readable."""
	ids = [s["id"] for s in subscriptions] if subscriptions else None
	findings, errors = [], []
	for detect in DETECTORS:
		try:
			found = detect(ids, settings)
			print(f"  {detect.__name__:<26} {len(found):>3} candidate(s)", file=sys.stderr)
			findings.extend(found)
		except Exception as exc:
			errors.append({"detector": detect.__name__, "error": str(exc)})
			print(f"  {detect.__name__:<26} FAILED: {exc}", file=sys.stderr)

	findings.sort(key=lambda f: f.monthly_cost_usd or 0, reverse=True)
	result = {
		"scanned_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
		"scope": ids or "all accessible subscriptions",
		"scope_label": scope_label(subscriptions),
		"settings": settings,
		"findings": [asdict(f) for f in findings],
		"errors": errors,
	}
	out.mkdir(parents=True, exist_ok=True)
	(out / "findings.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
	return result


def print_summary(result: dict) -> None:
	findings = result["findings"]
	total = sum(f["monthly_cost_usd"] or 0 for f in findings)
	print(f"\n{len(findings)} candidates, ~${total:,.2f}/month at list price")
	for f in findings:
		cost = f"${f['monthly_cost_usd']:,.2f}" if f["monthly_cost_usd"] is not None else "n/a"
		print(f"  {f['id']}  {cost:>10}/mo  {f['detector']:<28} {f['resource_name']}  [{f['owner']}]")
