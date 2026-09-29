import boto3
from botocore.exceptions import ClientError
from aws_region import get_region

region = get_region()
ec2 = boto3.client("ec2", region_name=region)

# Fetch all snapshots owned by this account (paginated)
snapshots = []
for page in ec2.get_paginator("describe_snapshots").paginate(OwnerIds=["self"]):
    snapshots.extend(page["Snapshots"])

if not snapshots:
    raise SystemExit(f"No snapshots found in {region}.")

def snap_name(s):
    return next((t["Value"] for t in s.get("Tags", []) if t["Key"] == "Name"), "-")

snapshots.sort(key=lambda s: s["StartTime"])

def show(items):
    fmt = "{:<4} {:<23} {:>7} {:<10} {:<17} {}"
    print(fmt.format("#", "SNAPSHOT ID", "SIZE", "STATE", "CREATED (UTC)", "NAME"))
    print("-" * 95)
    for n, s in enumerate(items, 1):
        print(fmt.format(n, s["SnapshotId"], f"{s['VolumeSize']} GB", s["State"],
                         s["StartTime"].strftime("%Y-%m-%d %H:%M"), snap_name(s)))

print(f"Found {len(snapshots)} snapshot(s) in {region}:\n")
show(snapshots)

# Optional filter by name substring
flt = input("\nFilter by name containing (Enter = no filter): ").strip().lower()
targets = [s for s in snapshots if flt in snap_name(s).lower()] if flt else snapshots

if not targets:
    raise SystemExit("Nothing matches that filter.")

if flt:
    print()
    show(targets)

# Choose which to delete
choice = input("\nDelete which? 'all' or numbers like 1,3,5 (Enter = cancel): ").strip().lower()
if not choice:
    raise SystemExit("Cancelled, nothing deleted.")

if choice == "all":
    selected = targets
else:
    try:
        idx = {int(x) for x in choice.split(",")}
        selected = [targets[i - 1] for i in sorted(idx) if 1 <= i <= len(targets)]
    except ValueError:
        raise SystemExit("Invalid input, nothing deleted.")

if not selected:
    raise SystemExit("No valid selection, nothing deleted.")

total_gb = sum(s["VolumeSize"] for s in selected)
print(f"\nAbout to PERMANENTLY delete {len(selected)} snapshot(s) ({total_gb} GB of source volumes) in {region}:")
for s in selected:
    print(f"  {s['SnapshotId']}  {snap_name(s)}")

if input("\nType 'delete' to confirm: ").strip() != "delete":
    raise SystemExit("Aborted, nothing deleted.")

for s in selected:
    try:
        ec2.delete_snapshot(SnapshotId=s["SnapshotId"])
        print("Deleted", s["SnapshotId"])
    except ClientError as e:
        print("FAILED ", s["SnapshotId"], "-", e.response["Error"]["Message"])
