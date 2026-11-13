"""The style guide's examples: rotated per run, and inside the persona's limits."""

import random
import re

from roastbot import agent, style

EXAMPLES = {name: examples for name, _, examples in style.PATTERNS}
ALL = [line for examples in EXAMPLES.values() for line in examples]
SWEARING = re.compile(r"fuck|shit|goddamn|damn|hell\b|ass|bastard|piss", re.I)


def test_rotation_shows_one_example_per_pattern():
	guide = style.render(random.Random(1))
	for name, _, examples in style.PATTERNS:
		assert f"{name}:" in guide
		assert sum(line in guide for line in examples) == 1, name
	assert style.NEVER in guide


def test_rotation_varies_between_runs():
	assert len({style.render(random.Random(seed)) for seed in range(10)}) > 1


def test_system_prompt_is_persona_plus_style():
	prompt = agent.system_prompt(random.Random(0))
	assert prompt.startswith(agent.PERSONA) and style.NEVER in prompt


def test_examples_follow_the_persona():
	for line in ALL:
		assert SWEARING.search(line), line  # the persona makes swearing mandatory
	for line in EXAMPLES["Owner jab"]:
		assert len(line.split()) <= 15, line
		assert not re.match(r"[\w() -]+:", line), line  # the report prints the owner beside the jab already
	# No epithet examples: short titles get copied verbatim. The persona's title list is the only inspiration.
	assert "Epithet" not in EXAMPLES
	assert not any("@" in line or "*" in line for line in ALL)  # no emails, no censored swearing
