import boto3
from botocore.exceptions import ClientError
from aws_region import get_region

region = get_region()
elbv2 = boto3.client("elbv2", region_name=region)

tgs = []
for page in elbv2.get_paginator("describe_target_groups").paginate():
    tgs.extend(page["TargetGroups"])

if not tgs:
    raise SystemExit(f"No target groups found in {region}.")

def lb_names(tg):
    # Names of load balancers using this target group (parsed from ARNs)
    return ", ".join(arn.split("/")[2] for arn in tg.get("LoadBalancerArns", [])) or "-"

def target_count(tg):
    try:
        health = elbv2.describe_target_health(TargetGroupArn=tg["TargetGroupArn"])
        return str(len(health["TargetHealthDescriptions"]))
    except ClientError:
        return "?"

tgs.sort(key=lambda t: t["TargetGroupName"].lower())

fmt = "{:<4} {:<28} {:<9} {:>5} {:<9} {:<22} {:>7}  {}"
print(f"Found {len(tgs)} target group(s) in {region}:\n")
print(fmt.format("#", "NAME", "PROTOCOL", "PORT", "TYPE", "VPC", "TARGETS", "USED BY LOAD BALANCER"))
print("-" * 125)
for n, t in enumerate(tgs, 1):
    print(fmt.format(n, t["TargetGroupName"], t.get("Protocol", "-"), t.get("Port", "-"),
                     t.get("TargetType", "-"), t.get("VpcId", "-"), target_count(t), lb_names(t)))

choice = input("\nDelete which? 'all', 'unused' (not attached to any load balancer), "
               "or numbers like 1,3 (Enter = cancel): ").strip().lower()
if not choice:
    raise SystemExit("Cancelled, nothing deleted.")

if choice == "all":
    selected = tgs
elif choice == "unused":
    selected = [t for t in tgs if not t.get("LoadBalancerArns")]
else:
    try:
        idx = {int(x) for x in choice.split(",")}
        selected = [tgs[i - 1] for i in sorted(idx) if 1 <= i <= len(tgs)]
    except ValueError:
        raise SystemExit("Invalid input, nothing deleted.")

if not selected:
    raise SystemExit("No valid selection, nothing deleted.")

print(f"\nAbout to PERMANENTLY delete {len(selected)} target group(s) in {region}:")
for t in selected:
    print(f"  {t['TargetGroupName']}  (used by: {lb_names(t)})")

in_use = [t for t in selected if t.get("LoadBalancerArns")]
if in_use:
    print(f"\nWARNING: {len(in_use)} of these are still attached to a load balancer. "
          "AWS will refuse to delete them until the load balancer or its listener rule is removed.")

if input("\nType 'delete' to confirm: ").strip() != "delete":
    raise SystemExit("Aborted, nothing deleted.")

for t in selected:
    try:
        elbv2.delete_target_group(TargetGroupArn=t["TargetGroupArn"])
        print("Deleted ", t["TargetGroupName"])
    except ClientError as e:
        print("FAILED  ", t["TargetGroupName"], "-", e.response["Error"]["Message"])
