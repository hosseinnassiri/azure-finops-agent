"""Bump RoastBot's version and refresh the code bundled in the Claude Code plugin.

uv run --no-project python scripts/bump_version.py patch    # 0.2.0 -> 0.2.1 (also: minor, major, or 1.4.0)
uv run --no-project python scripts/bump_version.py --sync   # refresh the bundle only, keep the version

A bump updates pyproject.toml, plugins/roastbot/.claude-plugin/plugin.json and plugins/roastbot/app/pyproject.toml,
then syncs. A sync copies the read-only modules in BUNDLE into plugins/roastbot/app/roastbot/ and relocks it. CI runs
this at every release, so the plugin always ships the code of the version it claims. Prints the version.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
PLUGIN = ROOT / "plugins" / "roastbot"
PLUGIN_JSON = PLUGIN / ".claude-plugin" / "plugin.json"
APP = PLUGIN / "app"
VERSION_RE = re.compile(r'^version = "(\d+)\.(\d+)\.(\d+)"', re.M)
# What the skill runs: scan and report. No agent engines (they need the SDKs) and no demo (it creates and deletes
# Azure resources), so the plugin carries only read-only code.
BUNDLE = ["__init__", "cli", "cloud", "detectors", "guard", "pricing", "report", "scan"]


def next_version(current: tuple[int, int, int], how: str) -> str:
	major, minor, patch = current
	if how == "major":
		return f"{major + 1}.0.0"
	if how == "minor":
		return f"{major}.{minor + 1}.0"
	if how == "patch":
		return f"{major}.{minor}.{patch + 1}"
	if re.fullmatch(r"\d+\.\d+\.\d+", how):
		return how
	raise SystemExit(f"expected patch, minor, major, X.Y.Z or --sync, got {how!r}")


def replace(path: Path, old: str, new: str) -> None:
	text = path.read_text(encoding="utf-8")
	if text.count(old) != 1:
		raise SystemExit(f"{path.relative_to(ROOT)}: expected 1 x {old!r}, found {text.count(old)}")
	path.write_text(text.replace(old, new), encoding="utf-8", newline="")


def current_version() -> str:
	return ".".join(VERSION_RE.search(PYPROJECT.read_text(encoding="utf-8")).groups())


def sync() -> None:
	target = APP / "roastbot"
	shutil.rmtree(target, ignore_errors=True)
	target.mkdir(parents=True)
	for module in BUNDLE:
		shutil.copyfile(ROOT / "roastbot" / f"{module}.py", target / f"{module}.py")
	version = current_version()
	app = APP / "pyproject.toml"
	text = VERSION_RE.sub(f'version = "{version}"', app.read_text(encoding="utf-8"), count=1)
	app.write_text(text, encoding="utf-8", newline="")
	subprocess.run(["uv", "lock", "--quiet", "--project", str(APP)], check=True)


def main() -> int:
	how = sys.argv[1] if len(sys.argv) > 1 else "patch"
	if how != "--sync":
		old = current_version()
		new = next_version(tuple(int(p) for p in old.split(".")), how)
		if new == old:
			raise SystemExit(f"already at {old}")
		replace(PYPROJECT, f'version = "{old}"', f'version = "{new}"')
		replace(PLUGIN_JSON, f'"version": "{old}"', f'"version": "{new}"')
		subprocess.run(["uv", "lock", "--quiet"], cwd=ROOT, check=True)
	sync()
	print(current_version())
	return 0


if __name__ == "__main__":
	sys.exit(main())
