import boto3
from botocore.exceptions import ClientError
from aws_region import get_region

region = get_region()
ec2 = boto3.client("ec2", region_name=region)

flt = [{"Name": "state", "Values": ["pending", "available"]}]
nats = []
for page in ec2.get_paginator("describe_nat_gateways").paginate(Filter=flt):
    nats.extend(page["NatGateways"])

if not nats:
    raise SystemExit(f"No NAT gateways found in {region}.")

def name(n):
    return next((t["Value"] for t in n.get("Tags", []) if t["Key"] == "Name"), "-")

def eip(n):
    return ", ".join(a.get("PublicIp", "-") for a in n["NatGatewayAddresses"]) or "-"

fmt = "{:<4} {:<23} {:<22} {:<10} {:<16} {}"
print(f"Found {len(nats)} NAT gateway(s) in {region}:\n")
print(fmt.format("#", "NAT GATEWAY ID", "VPC", "STATE", "PUBLIC IP", "NAME"))
print("-" * 95)
for i, n in enumerate(nats, 1):
    print(fmt.format(i, n["NatGatewayId"], n["VpcId"], n["State"], eip(n), name(n)))

choice = input("\nDelete which? 'all' or numbers like 1,3 (Enter = cancel): ").strip().lower()
if not choice:
    raise SystemExit("Cancelled, nothing deleted.")
if choice == "all":
    selected = nats
else:
    try:
        idx = {int(x) for x in choice.split(",")}
        selected = [nats[i - 1] for i in sorted(idx) if 1 <= i <= len(nats)]
    except ValueError:
        raise SystemExit("Invalid input, nothing deleted.")
if not selected:
    raise SystemExit("No valid selection, nothing deleted.")

print(f"\nAbout to PERMANENTLY delete {len(selected)} NAT gateway(s) in {region}:")
for n in selected:
    print(f"  {n['NatGatewayId']}  {n['VpcId']}  {eip(n)}")
print("Private subnets routing through these will lose internet access.")
print("The Elastic IPs stay allocated (and billing) afterwards; release them with release-elastic-ips.py.")

if input("\nType 'delete' to confirm: ").strip() != "delete":
    raise SystemExit("Aborted, nothing deleted.")

for n in selected:
    try:
        ec2.delete_nat_gateway(NatGatewayId=n["NatGatewayId"])
        print("Deleting", n["NatGatewayId"])
    except ClientError as e:
        print("FAILED  ", n["NatGatewayId"], "-", e.response["Error"]["Message"])
