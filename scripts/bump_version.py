"""Bump RoastBot's version everywhere it's written, so a plugin release reaches users.

uv run --no-project python scripts/bump_version.py patch   # 0.2.0 -> 0.2.1 (also: minor, major, or 1.4.0)

Updates pyproject.toml, plugins/roastbot/.claude-plugin/plugin.json, the `@v<version>` uvx pins in the roast
skill, and uv.lock (via `uv lock`). Prints the new version. CI runs it on every release-worthy push to main;
tests/test_plugin.py fails if these drift apart.
"""

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
PLUGIN_JSON = ROOT / "plugins" / "roastbot" / ".claude-plugin" / "plugin.json"
SKILL = ROOT / "plugins" / "roastbot" / "skills" / "roast" / "SKILL.md"
VERSION_RE = re.compile(r'^version = "(\d+)\.(\d+)\.(\d+)"', re.M)


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
	raise SystemExit(f"expected patch, minor, major or X.Y.Z, got {how!r}")


def replace(path: Path, old: str, new: str, count: int) -> None:
	text = path.read_text(encoding="utf-8")
	if text.count(old) != count:
		raise SystemExit(f"{path.relative_to(ROOT)}: expected {count} x {old!r}, found {text.count(old)}")
	path.write_text(text.replace(old, new), encoding="utf-8", newline="")


def main() -> int:
	how = sys.argv[1] if len(sys.argv) > 1 else "patch"
	match = VERSION_RE.search(PYPROJECT.read_text(encoding="utf-8"))
	old = ".".join(match.groups())
	new = next_version(tuple(int(g) for g in match.groups()), how)
	if new == old:
		raise SystemExit(f"already at {old}")

	replace(PYPROJECT, f'version = "{old}"', f'version = "{new}"', 1)
	replace(PLUGIN_JSON, f'"version": "{old}"', f'"version": "{new}"', 1)
	replace(SKILL, f"azure-finops-agent@v{old} roastbot", f"azure-finops-agent@v{new} roastbot", 3)
	subprocess.run(["uv", "lock", "--quiet"], cwd=ROOT, check=True)
	print(new)
	return 0


if __name__ == "__main__":
	sys.exit(main())
