import boto3
from botocore.exceptions import ClientError
from aws_region import get_region

region = get_region()
ec2 = boto3.client("ec2", region_name=region)

flt = [{"Name": "vpc-endpoint-type", "Values": ["Interface", "GatewayLoadBalancer"]}]
eps = []
for page in ec2.get_paginator("describe_vpc_endpoints").paginate(Filters=flt):
    eps.extend(page["VpcEndpoints"])

if not eps:
    raise SystemExit(f"No interface endpoints found in {region}.")

def name(e):
    return next((t["Value"] for t in e.get("Tags", []) if t["Key"] == "Name"), "-")

fmt = "{:<4} {:<24} {:<45} {:<11} {:<22} {}"
print(f"Found {len(eps)} VPC endpoint(s) in {region}:\n")
print(fmt.format("#", "ENDPOINT ID", "SERVICE", "STATE", "VPC", "NAME"))
print("-" * 120)
for n, e in enumerate(eps, 1):
    print(fmt.format(n, e["VpcEndpointId"], e["ServiceName"], e["State"], e["VpcId"], name(e)))

choice = input("\nDelete which? 'all' or numbers like 1,3 (Enter = cancel): ").strip().lower()
if not choice:
    raise SystemExit("Cancelled, nothing deleted.")
if choice == "all":
    selected = eps
else:
    try:
        idx = {int(x) for x in choice.split(",")}
        selected = [eps[i - 1] for i in sorted(idx) if 1 <= i <= len(eps)]
    except ValueError:
        raise SystemExit("Invalid input, nothing deleted.")
if not selected:
    raise SystemExit("No valid selection, nothing deleted.")

print(f"\nAbout to PERMANENTLY delete {len(selected)} VPC endpoint(s) in {region}:")
for e in selected:
    print(f"  {e['VpcEndpointId']}  {e['ServiceName']}")
print("Anything privately reaching those services through the endpoint will stop working.")

if input("\nType 'delete' to confirm: ").strip() != "delete":
    raise SystemExit("Aborted, nothing deleted.")

try:
    resp = ec2.delete_vpc_endpoints(VpcEndpointIds=[e["VpcEndpointId"] for e in selected])
    failed = {u["ResourceId"]: u["Error"]["Message"] for u in resp.get("Unsuccessful", [])}
    for e in selected:
        if e["VpcEndpointId"] in failed:
            print("FAILED  ", e["VpcEndpointId"], "-", failed[e["VpcEndpointId"]])
        else:
            print("Deleting", e["VpcEndpointId"])
except ClientError as e:
    print("FAILED -", e.response["Error"]["Message"])
