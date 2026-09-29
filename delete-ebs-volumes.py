import boto3
from botocore.exceptions import ClientError
from aws_region import get_region

region = get_region()
ec2 = boto3.client("ec2", region_name=region)

vols = []
for page in ec2.get_paginator("describe_volumes").paginate():
    vols.extend(page["Volumes"])

if not vols:
    raise SystemExit(f"No volumes found in {region}.")

def name(v):
    return next((t["Value"] for t in v.get("Tags", []) if t["Key"] == "Name"), "-")

def attached(v):
    return v["Attachments"][0]["InstanceId"] if v["Attachments"] else "(unattached)"

fmt = "{:<4} {:<23} {:>7} {:<6} {:<11} {:<21} {}"
print(f"Found {len(vols)} volume(s) in {region}:\n")
print(fmt.format("#", "VOLUME ID", "SIZE", "TYPE", "STATE", "ATTACHED TO", "NAME"))
print("-" * 100)
for n, v in enumerate(vols, 1):
    print(fmt.format(n, v["VolumeId"], f"{v['Size']} GB", v["VolumeType"], v["State"], attached(v), name(v)))

choice = input("\nDelete which? 'all', 'available' (unattached only), or numbers like 1,3 (Enter = cancel): ").strip().lower()
if not choice:
    raise SystemExit("Cancelled, nothing deleted.")
if choice == "all":
    selected = vols
elif choice == "available":
    selected = [v for v in vols if v["State"] == "available"]
else:
    try:
        idx = {int(x) for x in choice.split(",")}
        selected = [vols[i - 1] for i in sorted(idx) if 1 <= i <= len(vols)]
    except ValueError:
        raise SystemExit("Invalid input, nothing deleted.")
if not selected:
    raise SystemExit("No valid selection, nothing deleted.")

print(f"\nAbout to PERMANENTLY delete {len(selected)} volume(s) ({sum(v['Size'] for v in selected)} GB) in {region}:")
for v in selected:
    print(f"  {v['VolumeId']}  {v['Size']} GB  {attached(v)}  {name(v)}")
if any(v["State"] == "in-use" for v in selected):
    print("\nWARNING: in-use volumes can't be deleted until you detach them or terminate their instance.")
print("Data on deleted volumes is gone unless you have a snapshot.")

if input("\nType 'delete' to confirm: ").strip() != "delete":
    raise SystemExit("Aborted, nothing deleted.")

for v in selected:
    try:
        ec2.delete_volume(VolumeId=v["VolumeId"])
        print("Deleted ", v["VolumeId"])
    except ClientError as e:
        print("FAILED  ", v["VolumeId"], "-", e.response["Error"]["Message"])
