import boto3
from aws_region import get_region

region = get_region()
ec2 = boto3.client("ec2", region_name=region)

# Collect all non-terminated instances
instances = []
for r in ec2.describe_instances()["Reservations"]:
    for i in r["Instances"]:
        if i["State"]["Name"] in ("terminated", "shutting-down"):
            continue
        name = next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), "-")
        vols = [
            (b["Ebs"]["VolumeId"], b["Ebs"]["DeleteOnTermination"])
            for b in i.get("BlockDeviceMappings", []) if "Ebs" in b
        ]
        instances.append({"id": i["InstanceId"], "name": name,
                          "state": i["State"]["Name"], "vols": vols})

if not instances:
    raise SystemExit(f"No instances found in {region}.")

print(f"Instances in {region}:")
for inst in instances:
    print(f"  {inst['name']:<32} {inst['id']}  ({inst['state']})")

# Ask which one to keep (matches Name tag or instance ID)
keep_input = input("\nEnter the name (or ID) of the instance to KEEP: ").strip()
keep = [i for i in instances if keep_input in (i["name"], i["id"])]

if len(keep) == 0:
    raise SystemExit(f"No instance matches '{keep_input}'. Nothing changed.")
if len(keep) > 1:
    raise SystemExit(f"'{keep_input}' matches {len(keep)} instances. Use the instance ID instead.")

keep = keep[0]
remove = [i for i in instances if i["id"] != keep["id"]]

print(f"\nKEEP:   {keep['name']}  {keep['id']}")

if not remove:
    raise SystemExit("Nothing else to remove.")

print("\nREMOVE:")
for inst in remove:
    print(f"  {inst['name']}  {inst['id']}")
    for vid, dot in inst["vols"]:
        print(f"      {vid}  delete-on-termination={dot}")

# Optional snapshots
if input("\nSnapshot the volumes to be removed first? (yes/no): ").strip().lower() == "yes":
    snap_ids = []
    for inst in remove:
        for vid, _ in inst["vols"]:
            s = ec2.create_snapshot(
                VolumeId=vid,
                Description=f"backup of {inst['name']}",
                TagSpecifications=[{
                    "ResourceType": "snapshot",
                    "Tags": [{"Key": "Name", "Value": f"{inst['name']}-backup"}],
                }],
            )
            snap_ids.append(s["SnapshotId"])
            print("Snapshot", s["SnapshotId"], "for", inst["name"], vid)
    if snap_ids:
        print("Waiting for snapshots to complete (this can take several minutes)...")
        ec2.get_waiter("snapshot_completed").wait(
            SnapshotIds=snap_ids, WaiterConfig={"Delay": 15, "MaxAttempts": 120})
        print("Snapshots complete.")

# Final confirmation
print(f"\nThis will PERMANENTLY terminate {len(remove)} instance(s) in {region} and keep only '{keep['name']}'.")
if input("Type 'terminate' to confirm: ").strip() == "terminate":
    ec2.terminate_instances(InstanceIds=[i["id"] for i in remove])
    print("Terminating. Your kept instance was not touched.")
else:
    print("Aborted, nothing terminated.")
