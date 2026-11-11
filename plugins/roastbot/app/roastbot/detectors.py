"""Waste detectors. Each is a Resource Graph query plus a function that turns rows into Findings.

To add a detector: write a function taking (subscriptions, settings) and returning
list[Finding], then add it to DETECTORS at the bottom.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from . import cloud, pricing

OWNER_TAG_KEYS = ("owner", "createdby", "created-by", "created_by", "contact", "team")

COMMON = "id, name, type, resourceGroup, subscriptionId, location, tags"


@dataclass
class Finding:
	id: str
	detector: str
	title: str
	resource_id: str
	resource_name: str
	resource_type: str
	resource_group: str
	subscription_id: str
	location: str
	owner: str
	sku: str
	monthly_cost_usd: float | None
	cost_basis: str
	fix_summary: str
	fix_command: str
	evidence: dict = field(default_factory=dict)


def owner_of(row: dict) -> str:
	tags = {k.lower(): v for k, v in (row.get("tags") or {}).items()}
	for key in OWNER_TAG_KEYS:
		if tags.get(key):
			return str(tags[key])
	return f"unowned ({row['resourceGroup']})"


def make(row: dict, detector: str, **kwargs) -> Finding:
	digest = hashlib.sha1(f"{detector}:{row['id'].lower()}".encode()).hexdigest()[:8]
	return Finding(
		id=f"f-{digest}",
		detector=detector,
		resource_id=row["id"],
		resource_name=row["name"],
		resource_type=row["type"],
		resource_group=row["resourceGroup"],
		subscription_id=row["subscriptionId"],
		location=row["location"],
		owner=owner_of(row),
		**kwargs,
	)


def unattached_disks(subscriptions, settings) -> list[Finding]:
	rows = cloud.resource_graph(
		f"""
        Resources
        | where type =~ 'microsoft.compute/disks'
        | where properties.diskState =~ 'Unattached'
        | project {COMMON}, skuName = tostring(sku.name), sizeGb = toint(properties.diskSizeGB),
                  created = tostring(properties.timeCreated)
    """,
		subscriptions,
	)
	findings = []
	for r in rows:
		cost, tier = pricing.disk_monthly(r["skuName"], r["sizeGb"] or 0)
		findings.append(
			make(
				r,
				"unattached_disk",
				title="Unattached managed disk",
				sku=f"{r['skuName']} {r['sizeGb']} GiB ({tier})",
				monthly_cost_usd=cost,
				cost_basis="list price for the provisioned disk tier",
				fix_summary="Snapshot it if the data matters, then delete the disk.",
				fix_command=f"az disk delete --ids {r['id']} --yes",
				evidence={"disk_state": "Unattached", "created": r["created"]},
			)
		)
	return findings


def orphaned_public_ips(subscriptions, settings) -> list[Finding]:
	rows = cloud.resource_graph(
		f"""
        Resources
        | where type =~ 'microsoft.network/publicipaddresses'
        | where isnull(properties.ipConfiguration) and isnull(properties.natGateway)
        | project {COMMON}, skuName = tostring(sku.name),
                  allocation = tostring(properties.publicIPAllocationMethod),
                  ip = tostring(properties.ipAddress)
    """,
		subscriptions,
	)
	return [
		make(
			r,
			"orphaned_public_ip",
			title="Public IP attached to nothing",
			sku=f"{r['skuName']} / {r['allocation']}",
			monthly_cost_usd=pricing.public_ip_monthly(r["skuName"], r["allocation"]),
			cost_basis="list price per IP-hour",
			fix_summary="Delete it (check DNS records and firewall allow-lists that reference the address first).",
			fix_command=f"az network public-ip delete --ids {r['id']}",
			evidence={"ip_address": r["ip"] or "(none assigned)"},
		)
		for r in rows
	]


VM_QUERY = f"""
    Resources
    | where type =~ 'microsoft.compute/virtualmachines'
    | extend power = tostring(properties.extended.instanceView.powerState.code)
    | where power =~ '{{power}}'
    | project {COMMON}, vmSize = tostring(properties.hardwareProfile.vmSize),
              osType = tostring(properties.storageProfile.osDisk.osType), power
"""


def stopped_vms(subscriptions, settings) -> list[Finding]:
	rows = cloud.resource_graph(VM_QUERY.format(power="PowerState/stopped"), subscriptions)
	return [
		make(
			r,
			"stopped_not_deallocated_vm",
			title="VM stopped but not deallocated (compute still billing)",
			sku=r["vmSize"],
			monthly_cost_usd=pricing.vm_monthly(r["vmSize"], r["location"], r["osType"]),
			cost_basis="pay-as-you-go compute list price; a stopped VM still holds its hardware",
			fix_summary="Deallocate it. Stopping from inside the OS does not release the hardware.",
			fix_command=f"az vm deallocate --ids {r['id']}",
			evidence={"power_state": r["power"], "os": r["osType"]},
		)
		for r in rows
	]


def running_vms(subscriptions, settings) -> list[Finding]:
	"""Candidates only: the agent checks CPU through Azure Monitor (Azure MCP) and dismisses busy VMs."""
	rows = cloud.resource_graph(VM_QUERY.format(power="PowerState/running"), subscriptions)
	return [
		make(
			r,
			"running_vm_unverified",
			title="Running VM (CPU not yet checked)",
			sku=r["vmSize"],
			monthly_cost_usd=pricing.vm_monthly(r["vmSize"], r["location"], r["osType"]),
			cost_basis="pay-as-you-go compute list price",
			fix_summary="If it's idle: deallocate it, add auto-shutdown, or move it to a smaller size.",
			fix_command=f"az vm deallocate --ids {r['id']}",
			evidence={"power_state": r["power"], "os": r["osType"]},
		)
		for r in rows
	]


def empty_app_service_plans(subscriptions, settings) -> list[Finding]:
	rows = cloud.resource_graph(
		f"""
        Resources
        | where type =~ 'microsoft.web/serverfarms'
        | where toint(properties.numberOfSites) == 0
        | where tostring(sku.tier) !in~ ('Free', 'Shared', 'Dynamic', 'FlexConsumption')
        | project {COMMON}, skuName = tostring(sku.name), tier = tostring(sku.tier),
                  workers = toint(sku.capacity), isLinux = tobool(properties.reserved)
    """,
		subscriptions,
	)
	return [
		make(
			r,
			"empty_app_service_plan",
			title="App Service plan hosting zero apps",
			sku=f"{r['skuName']} x{r['workers'] or 1} ({'Linux' if r['isLinux'] else 'Windows'})",
			monthly_cost_usd=pricing.app_service_plan_monthly(
				r["skuName"], r["location"], bool(r["isLinux"]), r["workers"] or 1
			),
			cost_basis="pay-as-you-go list price x worker count",
			fix_summary="Delete the plan. An empty plan bills exactly like a busy one.",
			fix_command=f"az appservice plan delete --ids {r['id']} --yes",
			evidence={"apps_hosted": 0, "tier": r["tier"]},
		)
		for r in rows
	]


def orphaned_nics(subscriptions, settings) -> list[Finding]:
	rows = cloud.resource_graph(
		f"""
        Resources
        | where type =~ 'microsoft.network/networkinterfaces'
        | where isnull(properties.virtualMachine) and isnull(properties.privateEndpoint)
              and isnull(properties.privateLinkService)
        | project {COMMON}, privateIp = tostring(properties.ipConfigurations[0].properties.privateIPAddress)
    """,
		subscriptions,
	)
	return [
		make(
			r,
			"orphaned_nic",
			title="Network interface with no VM",
			sku="n/a",
			monthly_cost_usd=0.0,
			cost_basis="free, but it holds a private IP and clutters the subnet",
			fix_summary="Delete it to release the subnet IP.",
			fix_command=f"az network nic delete --ids {r['id']}",
			evidence={"private_ip": r["privateIp"]},
		)
		for r in rows
	]


def old_snapshots(subscriptions, settings) -> list[Finding]:
	rows = cloud.resource_graph(
		f"""
        Resources
        | where type =~ 'microsoft.compute/snapshots'
        | extend created = todatetime(properties.timeCreated)
        | where created < ago({int(settings["snapshot_age_days"])}d)
        | project {COMMON}, skuName = tostring(sku.name), sizeGb = toint(properties.diskSizeGB),
                  created = tostring(created)
    """,
		subscriptions,
	)
	return [
		make(
			r,
			"old_snapshot",
			title=f"Snapshot older than {settings['snapshot_age_days']} days",
			sku=f"{r['skuName']} {r['sizeGb']} GiB",
			monthly_cost_usd=pricing.snapshot_monthly(r["skuName"], r["sizeGb"] or 0),
			cost_basis="upper bound: snapshots bill on used bytes, not provisioned size",
			fix_summary="Delete it, or move long-term backups to Azure Backup with a retention policy.",
			fix_command=f"az snapshot delete --ids {r['id']}",
			evidence={"created": r["created"]},
		)
		for r in rows
	]


DETECTORS = [
	unattached_disks,
	orphaned_public_ips,
	stopped_vms,
	running_vms,
	empty_app_service_plans,
	orphaned_nics,
	old_snapshots,
]
