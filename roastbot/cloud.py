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
