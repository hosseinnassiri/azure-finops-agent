"""Read-only Resource Graph sweep.

Azure MCP Server has no Resource Graph tool, so the subscription-wide sweep for
orphaned resources lives here. Everything else (VM state, CPU metrics, activity log,
pricing, Advisor) the agent does through Azure MCP. Nothing here mutates Azure.
"""

from __future__ import annotations

from functools import lru_cache

from azure.identity import DefaultAzureCredential
from azure.mgmt.resourcegraph import ResourceGraphClient
from azure.mgmt.resourcegraph.models import QueryRequest, QueryRequestOptions


@lru_cache(maxsize=1)
def credential() -> DefaultAzureCredential:
	# Locally this resolves to your `az login`; in Azure, to the Reader-scoped managed identity.
	return DefaultAzureCredential(exclude_interactive_browser_credential=True)


def resource_graph(query: str, subscriptions: list[str] | None = None) -> list[dict]:
	"""Run a Resource Graph query, following skip tokens. No subscriptions = everything the identity can read."""
	client = ResourceGraphClient(credential())
	rows: list[dict] = []
	skip_token = None
	while True:
		response = client.resources(
			QueryRequest(
				query=query,
				subscriptions=subscriptions or None,
				options=QueryRequestOptions(result_format="objectArray", skip_token=skip_token),
			)
		)
		rows.extend(response.data)
		skip_token = response.skip_token
		if not skip_token:
			return rows


SUBSCRIPTIONS_QUERY = """
    ResourceContainers
    | where type =~ 'microsoft.resources/subscriptions'
    | project subscriptionId, name
"""


class SubscriptionError(ValueError):
	pass


def match_subscriptions(refs: list[str], visible: list[dict]) -> list[dict]:
	"""Resolve subscription IDs or display names (case-insensitive) to [{"id", "name"}], deduplicated, in order."""
	resolved: list[dict] = []
	for ref in refs:
		key = ref.strip().lower()
		hits = [s for s in visible if key in (s["subscriptionId"].lower(), s["name"].lower())]
		if not hits:
			names = ", ".join(sorted(s["name"] for s in visible)) or "none"
			raise SubscriptionError(
				f"Subscription {ref!r} not found or not readable by this identity in the current tenant "
				f"(visible: {names}). For another tenant, run `az account set --subscription <id>` first."
			)
		if len(hits) > 1:
			ids = ", ".join(s["subscriptionId"] for s in hits)
			raise SubscriptionError(f"Subscription name {ref!r} is ambiguous ({ids}). Pass the ID instead.")
		sub = {"id": hits[0]["subscriptionId"], "name": hits[0]["name"]}
		if sub not in resolved:
			resolved.append(sub)
	return resolved


def resolve_subscriptions(refs: list[str] | None) -> list[dict] | None:
	"""Look up --subscription values in Resource Graph. None means no filter: every readable subscription."""
	if not refs:
		return None
	return match_subscriptions(refs, resource_graph(SUBSCRIPTIONS_QUERY))
