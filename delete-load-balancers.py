import boto3
from botocore.exceptions import ClientError
from aws_region import get_region

region = get_region()
elbv2 = boto3.client("elbv2", region_name=region)
elb = boto3.client("elb", region_name=region)  # Classic load balancers

lbs = []

# ALB / NLB / GWLB
for page in elbv2.get_paginator("describe_load_balancers").paginate():
    for lb in page["LoadBalancers"]:
        protected = False
        try:
            attrs = elbv2.describe_load_balancer_attributes(
                LoadBalancerArn=lb["LoadBalancerArn"])["Attributes"]
            protected = any(a["Key"] == "deletion_protection.enabled" and a["Value"] == "true"
                            for a in attrs)
        except ClientError:
            pass
        lbs.append({
            "kind": "v2",
            "name": lb["LoadBalancerName"],
            "type": lb["Type"],
            "state": lb["State"]["Code"],
            "scheme": lb.get("Scheme", "-"),
            "vpc": lb.get("VpcId", "-"),
            "created": lb["CreatedTime"].strftime("%Y-%m-%d %H:%M"),
            "protected": protected,
            "arn": lb["LoadBalancerArn"],
        })

# Classic ELBs
try:
    for page in elb.get_paginator("describe_load_balancers").paginate():
        for lb in page["LoadBalancerDescriptions"]:
            lbs.append({
                "kind": "classic",
                "name": lb["LoadBalancerName"],
                "type": "classic",
                "state": "-",
                "scheme": lb.get("Scheme", "-"),
                "vpc": lb.get("VPCId", "-"),
                "created": lb["CreatedTime"].strftime("%Y-%m-%d %H:%M"),
                "protected": False,
                "arn": None,
            })
except ClientError as e:
    print("Could not list Classic load balancers:", e.response["Error"]["Message"])

if not lbs:
    raise SystemExit(f"No load balancers found in {region}.")

lbs.sort(key=lambda l: l["created"])

fmt = "{:<4} {:<24} {:<12} {:<10} {:<16} {:<22} {:<5} {}"
print(f"Found {len(lbs)} load balancer(s) in {region}:\n")
print(fmt.format("#", "NAME", "TYPE", "STATE", "SCHEME", "VPC", "PROT", "CREATED (UTC)"))
print("-" * 115)
for n, l in enumerate(lbs, 1):
    print(fmt.format(n, l["name"], l["type"], l["state"], l["scheme"], l["vpc"],
                     "yes" if l["protected"] else "no", l["created"]))

choice = input("\nDelete which? 'all' or numbers like 1,3 (Enter = cancel): ").strip().lower()
if not choice:
    raise SystemExit("Cancelled, nothing deleted.")

if choice == "all":
    selected = lbs
else:
    try:
        idx = {int(x) for x in choice.split(",")}
        selected = [lbs[i - 1] for i in sorted(idx) if 1 <= i <= len(lbs)]
    except ValueError:
        raise SystemExit("Invalid input, nothing deleted.")

if not selected:
    raise SystemExit("No valid selection, nothing deleted.")

print(f"\nAbout to PERMANENTLY delete {len(selected)} load balancer(s) in {region}:")
for l in selected:
    print(f"  {l['name']}  ({l['type']}, {l['vpc']})")
print("\nAnything routing traffic through these (DNS records, apps) will stop working.")

if input("\nType 'delete' to confirm: ").strip() != "delete":
    raise SystemExit("Aborted, nothing deleted.")

# Deletion protection blocks deletes, so offer to switch it off
protected = [l for l in selected if l["protected"]]
if protected:
    print(f"\n{len(protected)} selected load balancer(s) have deletion protection enabled:")
    for l in protected:
        print("  ", l["name"])
    if input("Type 'disable' to turn protection off for them (anything else skips them): ").strip() == "disable":
        for l in protected:
            try:
                elbv2.modify_load_balancer_attributes(
                    LoadBalancerArn=l["arn"],
                    Attributes=[{"Key": "deletion_protection.enabled", "Value": "false"}],
                )
                l["protected"] = False
                print("Protection disabled for", l["name"])
            except ClientError as e:
                print("FAILED to disable protection for", l["name"], "-", e.response["Error"]["Message"])

for l in selected:
    if l["protected"]:
        print("Skipped ", l["name"], "(deletion protection still on)")
        continue
    try:
        if l["kind"] == "v2":
            elbv2.delete_load_balancer(LoadBalancerArn=l["arn"])
        else:
            elb.delete_load_balancer(LoadBalancerName=l["name"])
        print("Deleted ", l["name"])
    except ClientError as e:
        print("FAILED  ", l["name"], "-", e.response["Error"]["Message"])

print("\nDeletion can take a minute or two to finish in AWS.")
