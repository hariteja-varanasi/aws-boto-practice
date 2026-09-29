import boto3
from botocore.exceptions import ClientError
from aws_region import get_region

region = get_region()
ec2 = boto3.client("ec2", region_name=region)

items = []
flt = [{"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]}]
for page in ec2.get_paginator("describe_instances").paginate(Filters=flt):
    for r in page["Reservations"]:
        for i in r["Instances"]:
            name = next((t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), "-")
            items.append({"id": i["InstanceId"], "name": name, "type": i["InstanceType"],
                          "state": i["State"]["Name"]})

if not items:
    raise SystemExit(f"No instances found in {region}.")

fmt = "{:<4} {:<21} {:<14} {:<10} {}"
print(f"Found {len(items)} instance(s) in {region}:\n")
print(fmt.format("#", "INSTANCE ID", "TYPE", "STATE", "NAME"))
print("-" * 80)
for n, x in enumerate(items, 1):
    print(fmt.format(n, x["id"], x["type"], x["state"], x["name"]))

choice = input("\nTerminate which? 'all' or numbers like 1,3 (Enter = cancel): ").strip().lower()
if not choice:
    raise SystemExit("Cancelled, nothing terminated.")
if choice == "all":
    selected = items
else:
    try:
        idx = {int(x) for x in choice.split(",")}
        selected = [items[i - 1] for i in sorted(idx) if 1 <= i <= len(items)]
    except ValueError:
        raise SystemExit("Invalid input, nothing terminated.")
if not selected:
    raise SystemExit("No valid selection, nothing terminated.")

print(f"\nAbout to PERMANENTLY terminate {len(selected)} instance(s) in {region}:")
for x in selected:
    print(f"  {x['id']}  {x['name']}  ({x['state']})")
print("Their root volumes are deleted too if 'delete on termination' is set.")

if input("\nType 'terminate' to confirm: ").strip() != "terminate":
    raise SystemExit("Aborted, nothing terminated.")

for x in selected:
    try:
        ec2.terminate_instances(InstanceIds=[x["id"]])
        print("Terminating", x["id"], x["name"])
    except ClientError as e:
        print("FAILED     ", x["id"], "-", e.response["Error"]["Message"])
