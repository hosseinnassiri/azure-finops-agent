"""Content check for the agent's roasts, via TypeSafe AI's Jev (a classifier: typed answers, no prose).

Opt-in with `roastbot roast --guard`. save_roasts sends every line Claude wrote to Jev, which scores it
against the persona's floor. Flagged lines go back to Claude for a rewrite, and anything still flagged
is dropped at render time so report.py's canned fallbacks take its place.

Fails open: if Jev can't run (no SDK, no key, API down), the roasts are kept and the report says UNCHECKED.
The SDK is an optional extra (`uv sync --extra guard`) and is imported only when a check actually runs.
"""

from __future__ import annotations

import asyncio
import copy
import datetime as dt
import os
from typing import Any

THRESHOLD = 0.5  # a line is flagged when any question's probability is at least this
MAX_REWRITES = 2  # rounds of "rewrite these" sent back to Claude before leftovers are dropped
CONCURRENCY = 8
TIMEOUT_S = 10.0
FINDING_FIELDS = ("roast", "fix_note", "epithet", "title")

ALLOWED = (
	"Profanity, swearing, sarcasm and harsh insults about competence, laziness or cloud spending are allowed. "
	"Team names, owner tags and Azure resource names are allowed."
)
# Mirrors the floor at the end of agent.PERSONA. Keep them in step.
CHECKS = {
	"protected_trait": "Does this text insult or demean someone because of their race, ethnicity, nationality, "
	"gender, sexuality, religion, disability, age, health or family?",
	"slur": "Does this text contain a slur (a derogatory term for a group of people)?",
	"threat": "Does this text threaten or encourage violence or physical harm against anyone?",
	"names_person": "Does this text contain an individual person's name, email address or username?",
}


def unavailable_reason() -> str | None:
	"""Why a check can't run here, or None if it can."""
	try:
		import typesafe_sdk  # noqa: F401
	except ImportError:
		return "typesafe-sdk isn't installed (run `uv sync --extra guard`)"
	if not os.environ.get("TYPESAFE_API_KEY"):
		return "TYPESAFE_API_KEY isn't set"
	return None


def texts(roasts: dict) -> list[tuple[list, str]]:
	"""Every line Claude wrote, with its path in the roasts object."""
	found: list[tuple[list, str]] = []
	if roasts.get("headline"):
		found.append((["headline"], roasts["headline"]))
	found += [(["owners", o], line) for o, line in roasts.get("owners", {}).items() if line]
	found += [(["insults", i], line) for i, line in enumerate(roasts.get("insults", [])) if line]
	for fid, verdict in roasts.get("findings", {}).items():
		found += [(["findings", fid, k], verdict[k]) for k in FINDING_FIELDS if verdict.get(k)]
		# Evidence too: activity-log callers can carry real names.
		found += [(["findings", fid, "evidence", k], str(v)) for k, v in verdict.get("evidence", {}).items() if v]
	return found


def questions() -> dict:
	from typesafe_sdk import Noul

	return {name: Noul(instructions=f"{question} {ALLOWED}") for name, question in CHECKS.items()}


async def check(roasts: dict, client: Any = None) -> dict:
	"""Score every line. Never raises: failures give status "unavailable", keeping whatever was flagged so far."""
	record: dict = {
		"status": "checked",
		"model": None,
		"checked_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
		"lines": 0,
		"flags": [],
	}
	if client is None and (reason := unavailable_reason()):
		return {**record, "status": "unavailable", "error": reason}
	try:
		if client is None:
			from typesafe_sdk import AsyncTypeSafeClient

			async with AsyncTypeSafeClient(timeout=TIMEOUT_S) as live:
				await score_all(live, roasts, record)
		else:
			await score_all(client, roasts, record)
	except Exception as exc:  # fail open: the report says UNCHECKED instead of the run dying
		record.update(status="unavailable", error=f"{type(exc).__name__}: {exc}"[:200])
	return record


async def score_all(client: Any, roasts: dict, record: dict) -> None:
	items = texts(roasts)
	asked = questions() if items else {}
	gate = asyncio.Semaphore(CONCURRENCY)

	async def score(text: str):
		async with gate:
			return await client.system_one(state=text, questions=asked)

	results = await asyncio.gather(*(score(text) for _, text in items), return_exceptions=True)
	record["lines"] = len(items)
	failures = [r for r in results if isinstance(r, BaseException)]
	for (path, text), result in zip(items, results, strict=True):
		if isinstance(result, BaseException):
			continue
		record["model"] = getattr(result, "model", None)
		hits = {q: round(a.noul, 3) for q, a in result.nouls.items() if a.noul >= THRESHOLD}
		if hits:
			record["flags"].append({"path": path, "text": text, "hits": hits})
	if failures:
		raise failures[0]


def feedback(record: dict) -> str:
	"""The tool result that sends flagged lines back to Claude."""
	lines = [
		f"Saved, but the content check flagged {len(record['flags'])} line(s). Rewrite ONLY these, just as savage "
		"minus the flagged part, then call save_roasts again with the full object:"
	]
	for flag in record["flags"]:
		why = ", ".join(f"{q} {p:.2f}" for q, p in flag["hits"].items())
		lines.append(f"- {'/'.join(map(str, flag['path']))} ({why}): {flag['text']!r}")
	return "\n".join(lines)


def apply(roasts: dict) -> dict:
	"""A copy of roasts without the lines the check flagged. Pure: needs neither the SDK nor the network."""
	flags = (roasts.get("guard") or {}).get("flags", [])
	if not flags:
		return roasts
	clean = copy.deepcopy(roasts)
	dropped_insults = set()
	for flag in flags:
		match flag["path"]:
			case ["headline"]:
				clean.pop("headline", None)
			case ["owners", owner]:
				clean.get("owners", {}).pop(owner, None)
			case ["insults", int(i)]:
				dropped_insults.add(i)
			case ["findings", fid, "evidence", key]:
				clean.get("findings", {}).get(fid, {}).get("evidence", {}).pop(key, None)
			case ["findings", fid, field]:
				clean.get("findings", {}).get(fid, {}).pop(field, None)
	if dropped_insults:
		clean["insults"] = [line for i, line in enumerate(clean.get("insults", [])) if i not in dropped_insults]
	return clean
