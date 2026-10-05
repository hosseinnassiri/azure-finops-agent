"""Plant realistic cloud waste in a throwaway resource group (and remove it again).

Cost while it exists: about $0.30/hour (mostly the P30 disk and two small VMs), so ~$4 overnight.
The idle-VM check needs a few hours of CPU metrics, so plant the evening before the demo.
"""

from __future__ import annotations

import shutil
import subprocess

TAGS = ["purpose=roastbot-demo"]
VM_SIZES = ["Standard_B2s", "Standard_B2ls_v2", "Standard_B2s_v2", "Standard_D2as_v5", "Standard_D2s_v5"]


def az(*args: str, capture: bool = False) -> str:
	exe = shutil.which("az")
	if exe is None:
		raise SystemExit("Azure CLI (az) not found on PATH.")
	result = subprocess.run(
		[exe, *args, *([] if capture else ["-o", "none"])], check=True, text=True, capture_output=capture
	)
	return (result.stdout or "").strip()


def owned(owner: str) -> list[str]:
	return ["--tags", f"owner={owner}", *TAGS]


def plant(rg: str, location: str) -> int:
	vm = ["--image", "Ubuntu2404", "--admin-username", "azureuser", "--generate-ssh-keys"]
	steps = [
		("Resource group", ["group", "create", "-n", rg, "-l", location, "--tags", *TAGS]),
		(
			"1/6 Unattached 1 TiB premium disk (team-data, ~$135/mo)",
			[
				"disk",
				"create",
				"-g",
				rg,
				"-n",
				"disk-old-migration-backup",
				"--size-gb",
				"1024",
				"--sku",
				"Premium_LRS",
				*owned("team-data"),
			],
		),
		(
			"2/6 Public IPs attached to nothing (team-web)",
			[
				"network",
				"public-ip",
				"create",
				"-g",
				rg,
				"-n",
				"pip-legacy-lb",
				"--sku",
				"Standard",
				"--allocation-method",
				"Static",
				*owned("team-web"),
			],
		),
		(
			None,
			[
				"network",
				"public-ip",
				"create",
				"-g",
				rg,
				"-n",
				"pip-test-do-not-delete",
				"--sku",
				"Standard",
				"--allocation-method",
				"Static",
				*owned("team-web"),
			],
		),
		(
			"3/6 VNet + orphaned NIC (team-platform)",
			[
				"network",
				"vnet",
				"create",
				"-g",
				rg,
				"-n",
				"vnet-roastbot",
				"--address-prefix",
				"10.42.0.0/16",
				"--subnet-name",
				"default",
				"--subnet-prefix",
				"10.42.0.0/24",
			],
		),
		(
			None,
			[
				"network",
				"nic",
				"create",
				"-g",
				rg,
				"-n",
				"nic-ghost-of-vm-past",
				"--vnet-name",
				"vnet-roastbot",
				"--subnet",
				"default",
				*owned("team-platform"),
			],
		),
		# Pre-created NICs mean az creates no public IP or NSG for the VMs.
		(
			"4/6 VM stopped but NOT deallocated (team-platform)",
			[
				"network",
				"nic",
				"create",
				"-g",
				rg,
				"-n",
				"nic-jumpbox",
				"--vnet-name",
				"vnet-roastbot",
				"--subnet",
				"default",
			],
		),
		(
			"5/6 Idle running VM (team-data): NIC first",
			[
				"network",
				"nic",
				"create",
				"-g",
				rg,
				"-n",
				"nic-etl-worker",
				"--vnet-name",
				"vnet-roastbot",
				"--subnet",
				"default",
			],
		),
	]
	failed = []
	for label, args in steps:
		if label:
			print(label)
		try:
			az(*args)
		except subprocess.CalledProcessError:
			failed.append(label or " ".join(args[:3]))

	# Small sizes hit regional capacity limits (SkuNotAvailable) a lot, so try a few until one sticks.
	for name, nic, owner in (
		("vm-jumpbox-stopped", "nic-jumpbox", "team-platform"),
		("vm-etl-worker-idle", "nic-etl-worker", "team-data"),
	):
		print(f"   creating {name}")
		for size in VM_SIZES:
			try:
				az("vm", "create", "-g", rg, "-n", name, "--nics", nic, *vm, "--size", size, *owned(owner))
				print(f"   created with {size}")
				break
			except subprocess.CalledProcessError:
				print(f"   {size} unavailable, trying the next size")
		else:
			failed.append(name)
	try:
		az("vm", "stop", "-g", rg, "-n", "vm-jumpbox-stopped")  # 'stop' keeps billing compute; 'deallocate' wouldn't
	except subprocess.CalledProcessError:
		failed.append("vm stop")

	print("6/6 Snapshot nobody will remember (team-platform)")
	try:
		os_disk = az(
			"vm",
			"show",
			"-g",
			rg,
			"-n",
			"vm-jumpbox-stopped",
			"--query",
			"storageProfile.osDisk.managedDisk.id",
			"-o",
			"tsv",
			capture=True,
		)
		az(
			"snapshot",
			"create",
			"-g",
			rg,
			"-n",
			"snap-before-upgrade-final-v2",
			"--source",
			os_disk,
			*owned("team-platform"),
		)
	except subprocess.CalledProcessError:
		failed.append("snapshot")

	if failed:
		print(f"\nDone, but these steps failed: {failed}")
		return 1
	print("\nDone. Tomorrow morning: uv run roastbot roast --demo")
	return 0


def cleanup(rg: str) -> int:
	print(az("group", "show", "-n", rg, "--query", "{name:name, tags:tags}", "-o", "json", capture=True))
	if input(f"Delete resource group '{rg}' and everything in it? Type 'yes': ").strip().lower() != "yes":
		print("Aborted.")
		return 1
	az("group", "delete", "-n", rg, "--yes", "--no-wait")
	print("Deletion started (Azure finishes it in the background).")
	return 0
