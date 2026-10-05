import pytest


@pytest.fixture
def make_finding():
    def _make(id_="f-1", detector="unattached_disk", owner="team-data", cost=100.0, **overrides):
        finding = {
            "id": id_,
            "detector": detector,
            "title": "A title",
            "resource_id": f"/subscriptions/s/{id_}",
            "resource_name": f"res-{id_}",
            "resource_type": "t",
            "resource_group": "rg",
            "subscription_id": "s",
            "location": "canadacentral",
            "owner": owner,
            "sku": "Premium_LRS",
            "monthly_cost_usd": cost,
            "cost_basis": "list",
            "fix_summary": "Delete it.",
            "fix_command": "az thing delete",
            "evidence": {},
        }
        return {**finding, **overrides}

    return _make
