import pytest

from roastbot import agent, scan
from roastbot.cloud import SubscriptionError, match_subscriptions

VISIBLE = [
	{"subscriptionId": "11111111-aaaa", "name": "Pay-As-You-Go"},
	{"subscriptionId": "22222222-bbbb", "name": "Sandbox"},
	{"subscriptionId": "33333333-cccc", "name": "Sandbox"},
]


def test_match_by_id_or_name_case_insensitive_and_deduplicated():
	subs = match_subscriptions(["pay-as-you-go", "11111111-AAAA", " 22222222-bbbb "], VISIBLE)
	assert subs == [{"id": "11111111-aaaa", "name": "Pay-As-You-Go"}, {"id": "22222222-bbbb", "name": "Sandbox"}]


def test_unknown_subscription_lists_what_is_visible():
	with pytest.raises(SubscriptionError, match="not found.*Pay-As-You-Go"):
		match_subscriptions(["Production"], VISIBLE)


def test_ambiguous_name_asks_for_the_id():
	with pytest.raises(SubscriptionError, match="ambiguous.*22222222-bbbb, 33333333-cccc"):
		match_subscriptions(["sandbox"], VISIBLE)


def test_scope_text():
	subs = [{"id": "11111111-aaaa", "name": "Pay-As-You-Go"}]
	assert scan.scope_label(None) == "all accessible subscriptions"
	assert scan.scope_label(subs) == "Pay-As-You-Go"
	assert "Pay-As-You-Go (11111111-aaaa)" in agent.scope_note(subs)
	assert agent.scope_note(None).startswith("every subscription")
