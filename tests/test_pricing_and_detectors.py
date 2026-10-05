from roastbot import pricing
from roastbot.detectors import make, owner_of


def test_disk_tiers():
    assert pricing.disk_monthly("Premium_LRS", 1024) == (135.17, "P30")
    assert pricing.disk_monthly("Premium_LRS", 1000) == (135.17, "P30")  # billed at the next tier up
    assert pricing.disk_monthly("StandardSSD_ZRS", 100) == (14.4, "E10")
    assert pricing.disk_monthly("Mystery_LRS", 10) == (None, "unknown")


def test_public_ip_and_snapshot_prices():
    assert pricing.public_ip_monthly("Standard", "Static") == 3.65
    assert pricing.public_ip_monthly("Basic", "Dynamic") == 0.0
    assert pricing.snapshot_monthly("Standard_LRS", 30) == 1.5


def test_owner_from_tags_case_insensitive():
    assert owner_of({"tags": {"Owner": "team-x"}, "resourceGroup": "rg"}) == "team-x"
    assert owner_of({"tags": {"createdBy": "team-y"}, "resourceGroup": "rg"}) == "team-y"
    assert owner_of({"tags": None, "resourceGroup": "rg-a"}) == "unowned (rg-a)"


def test_finding_ids_are_stable_and_case_insensitive():
    row = {
        "id": "/subscriptions/S/rg/X",
        "name": "x",
        "type": "t",
        "resourceGroup": "rg",
        "subscriptionId": "S",
        "location": "l",
        "tags": {},
    }
    kwargs = dict(title="t", sku="s", monthly_cost_usd=1.0, cost_basis="b", fix_summary="f", fix_command="c")
    a = make(row, "unattached_disk", **kwargs)
    b = make({**row, "id": row["id"].lower()}, "unattached_disk", **kwargs)
    assert a.id == b.id and a.id.startswith("f-")
