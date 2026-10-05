"""roastbot CLI.

uv run roastbot roast [--demo] [--subscription ID|NAME] [--guard]  # the agent: sweep, verify, roast, report
uv run roastbot scan [--demo] [--subscription ID|NAME]             # sweep only, no LLM
uv run roastbot report [--open]                                    # re-render the report from saved files
uv run roastbot demo plant | cleanup                               # plant / remove demo waste in a sandbox
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from . import agent, cloud, demo, guard, report, scan


def main(argv=None) -> int:
	parser = argparse.ArgumentParser(
		prog="roastbot", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
	)
	parser.add_argument("--out", default="out", type=Path)
	parser.add_argument("--model", help="Claude model id (default: your Claude Code default)")
	sub = parser.add_subparsers(dest="command", required=True)

	for name in ("roast", "scan"):
		p = sub.add_parser(name)
		p.add_argument(
			"--subscription",
			action="append",
			dest="subscriptions",
			metavar="ID|NAME",
			help="subscription ID or display name to roast; repeat for several (default: every one you can read)",
		)
		p.add_argument("--demo", action="store_true", help="short thresholds so freshly planted waste counts")
		p.add_argument("--no-open", action="store_true", help="don't open the report in a browser")
		if name == "roast":
			p.add_argument("--guard", action="store_true", help="content-check the roasts with Jev (TypeSafe AI)")

	p = sub.add_parser("report")
	p.add_argument("--open", action="store_true")

	p = sub.add_parser("demo")
	p.add_argument("action", choices=["plant", "cleanup"])
	p.add_argument("--location", default="canadacentral")
	p.add_argument("--resource-group", default="rg-roastbot-demo")

	args = parser.parse_args(argv)
	out: Path = args.out
	for stream in (sys.stdout, sys.stderr):  # Windows consoles default to cp1252; RoastBot needs its emoji
		stream.reconfigure(encoding="utf-8", errors="replace")

	if args.command in ("roast", "scan"):
		try:
			subscriptions = cloud.resolve_subscriptions(args.subscriptions)
		except cloud.SubscriptionError as exc:
			print(f"roastbot: {exc}", file=sys.stderr)
			return 2
		print(f"Scope: {scan.scope_label(subscriptions)}", file=sys.stderr)

	if args.command == "roast":
		if args.guard and (reason := guard.unavailable_reason()):
			print(f"Content check unavailable: {reason}. The report will be marked UNCHECKED.", file=sys.stderr)
		asyncio.run(agent.roast(out, subscriptions, args.demo, args.model, args.guard))
		if (out / "report.html").exists() and not args.no_open:
			report.finalize(out, open_browser=True)
	elif args.command == "scan":
		scan.print_summary(scan.run_scan(subscriptions, scan.settings_for(args.demo), out))
		print(f"\nReport: {report.finalize(out, open_browser=not args.no_open)}")
	elif args.command == "report":
		print(report.finalize(out, open_browser=args.open))
	elif args.command == "demo":
		return (
			demo.plant(args.resource_group, args.location)
			if args.action == "plant"
			else demo.cleanup(args.resource_group)
		)
	return 0


if __name__ == "__main__":
	sys.exit(main())
