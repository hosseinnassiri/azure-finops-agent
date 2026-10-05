"""Monthly cost estimates at pay-as-you-go list price.

VMs and App Service plans use the public Azure Retail Prices API (no auth).
Disks, snapshots and public IPs use a small East US list-price table, which is
close enough to roast with but is not an invoice. Actual spend (discounts,
reservations, savings plans) lives in Cost Management.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import requests

HOURS_PER_MONTH = 730
RETAIL_API = "https://prices.azure.com/api/retail/prices"
CACHE_FILE = Path("out/.price-cache.json")

# (max size GiB, USD/month, tier) for LRS managed disks, East US list price.
DISK_TIERS = {
	"Premium": [
		(4, 0.77, "P1"),
		(8, 1.54, "P2"),
		(16, 3.01, "P3"),
		(32, 5.28, "P4"),
		(64, 10.21, "P6"),
		(128, 19.71, "P10"),
		(256, 38.01, "P15"),
		(512, 73.22, "P20"),
		(1024, 135.17, "P30"),
		(2048, 259.05, "P40"),
		(4096, 495.57, "P50"),
		(8192, 946.08, "P60"),
		(16384, 1802.24, "P70"),
		(32767, 3604.48, "P80"),
	],
	"StandardSSD": [
		(4, 0.30, "E1"),
		(8, 0.60, "E2"),
		(16, 1.20, "E3"),
		(32, 2.40, "E4"),
		(64, 4.80, "E6"),
		(128, 9.60, "E10"),
		(256, 19.20, "E15"),
		(512, 38.40, "E20"),
		(1024, 76.80, "E30"),
		(2048, 153.60, "E40"),
		(4096, 307.20, "E50"),
		(8192, 614.40, "E60"),
		(16384, 1228.80, "E70"),
		(32767, 2457.60, "E80"),
	],
	"Standard": [
		(32, 1.54, "S4"),
		(64, 3.01, "S6"),
		(128, 5.89, "S10"),
		(256, 11.33, "S15"),
		(512, 21.76, "S20"),
		(1024, 40.96, "S30"),
		(2048, 77.83, "S40"),
		(4096, 143.36, "S50"),
		(8192, 262.14, "S60"),
		(16384, 524.29, "S70"),
		(32767, 1048.58, "S80"),
	],
}
PER_GB_DISKS = {"PremiumV2": 0.082, "UltraSSD": 0.12}  # capacity only; IOPS/throughput extra
ZRS_MULTIPLIER = 1.5

_cache: dict[str, list[dict]] | None = None


def _retail(filter_: str) -> list[dict]:
	global _cache
	if _cache is None:
		_cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
	if filter_ not in _cache:
		response = requests.get(RETAIL_API, params={"$filter": filter_}, timeout=30)
		response.raise_for_status()
		_cache[filter_] = response.json().get("Items", [])
		CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
		CACHE_FILE.write_text(json.dumps(_cache))
	return _cache[filter_]


def vm_monthly(vm_size: str, region: str, os_type: str) -> float | None:
	items = _retail(
		f"serviceName eq 'Virtual Machines' and armRegionName eq '{region}' "
		f"and armSkuName eq '{vm_size}' and priceType eq 'Consumption'"
	)
	windows = (os_type or "").lower() == "windows"
	for item in items:
		if "Spot" in item["skuName"] or "Low Priority" in item["skuName"]:
			continue
		if item["productName"].endswith("Windows") == windows:
			return round(item["unitPrice"] * HOURS_PER_MONTH, 2)
	return None


def app_service_plan_monthly(sku_name: str, region: str, linux: bool, workers: int) -> float | None:
	retail_sku = re.sub(r"(\d)(v\d)$", r"\1 \2", sku_name)  # ARM "P1v3" -> retail "P1 v3"
	items = _retail(
		f"serviceName eq 'Azure App Service' and armRegionName eq '{region}' "
		f"and skuName eq '{retail_sku}' and priceType eq 'Consumption'"
	)
	for item in items:
		if item["unitOfMeasure"] == "1 Hour" and item["productName"].endswith("Linux") == linux:
			return round(item["unitPrice"] * HOURS_PER_MONTH * max(workers, 1), 2)
	return None


def disk_monthly(sku_name: str, size_gb: int) -> tuple[float | None, str]:
	"""Returns (USD/month, tier label)."""
	family, _, redundancy = (sku_name or "").partition("_")
	multiplier = ZRS_MULTIPLIER if redundancy == "ZRS" else 1.0
	if family in PER_GB_DISKS:
		return round(PER_GB_DISKS[family] * size_gb, 2), family
	for max_gb, price, tier in DISK_TIERS.get(family, []):
		if size_gb <= max_gb:
			return round(price * multiplier, 2), tier
	return None, "unknown"


def snapshot_monthly(sku_name: str, size_gb: int) -> float:
	# Snapshots bill on used bytes, so provisioned size makes this an upper bound.
	per_gb = 0.12 if (sku_name or "").startswith("Premium") else 0.05
	return round(per_gb * size_gb, 2)


def public_ip_monthly(sku_name: str, allocation: str) -> float:
	if (sku_name or "").lower() == "standard":
		return round(0.005 * HOURS_PER_MONTH, 2)
	# Basic dynamic IPs are free while unassociated; Basic static ones are not.
	return round(0.0036 * HOURS_PER_MONTH, 2) if (allocation or "").lower() == "static" else 0.0
