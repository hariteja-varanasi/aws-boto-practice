import boto3
from botocore.exceptions import ClientError
from aws_region import get_region

region = get_region()
asg = boto3.client("autoscaling", region_name=region)

groups = []
for page in asg.get_paginator("describe_auto_scaling_groups").paginate():
    groups.extend(page["AutoScalingGroups"])

if not groups:
    raise SystemExit(f"No Auto Scaling groups found in {region}.")


def deleting(g):
    # "Status" is only present on a group while a delete is in progress
    return "Status" in g


fmt = "{:<4} {:<36} {:>4} {:>8} {:>4} {:>10}  {}"
print(f"Found {len(groups)} Auto Scaling group(s) in {region}:\n")
print(fmt.format("#", "NAME", "MIN", "DESIRED", "MAX", "INSTANCES", "STATUS"))
print("-" * 95)
for n, g in enumerate(groups, 1):
    print(fmt.format(n, g["AutoScalingGroupName"], g["MinSize"], g["DesiredCapacity"],
                     g["MaxSize"], len(g["Instances"]), g.get("Status", "-")))

deletable = [g for g in groups if not deleting(g)]
if not deletable:
    raise SystemExit("\nAll groups are already being deleted. Wait a few minutes and rerun.")

choice = input("\nDelete which? 'all' or numbers like 1,3 (Enter = cancel): ").strip().lower()
if not choice:
    raise SystemExit("Cancelled, nothing deleted.")
if choice == "all":
    selected = deletable
else:
    try:
        idx = {int(x) for x in choice.split(",")}
        picked = [groups[i - 1] for i in sorted(idx) if 1 <= i <= len(groups)]
    except ValueError:
        raise SystemExit("Invalid input, nothing deleted.")
    for g in picked:
        if deleting(g):
            print(f"Skipping {g['AutoScalingGroupName']} - already being deleted.")
    selected = [g for g in picked if not deleting(g)]
if not selected:
    raise SystemExit("No valid selection, nothing deleted.")

total = sum(len(g["Instances"]) for g in selected)
print(f"\nAbout to PERMANENTLY delete {len(selected)} Auto Scaling group(s) in {region}:")
for g in selected:
    print(f"  {g['AutoScalingGroupName']}  ({len(g['Instances'])} instance(s))")
print(f"Force delete also TERMINATES their {total} running instance(s).")

if input("\nType 'delete' to confirm: ").strip() != "delete":
    raise SystemExit("Aborted, nothing deleted.")

for g in selected:
    try:
        asg.delete_auto_scaling_group(AutoScalingGroupName=g["AutoScalingGroupName"], ForceDelete=True)
        print("Deleting", g["AutoScalingGroupName"])
    except ClientError as e:
        print("FAILED  ", g["AutoScalingGroupName"], "-", e.response["Error"]["Message"])

print("\nDeletion is asynchronous: groups show 'Delete in progress' until their instances finish terminating.")
print("Rerun this script in a few minutes to check.")