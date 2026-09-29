import boto3
from botocore.exceptions import ClientError
from aws_region import get_region

region = get_region()
ec2 = boto3.client("ec2", region_name=region)

addresses = ec2.describe_addresses()["Addresses"]

if not addresses:
    raise SystemExit(f"No Elastic IPs found in {region}.")

def eip_name(a):
    return next((t["Value"] for t in a.get("Tags", []) if t["Key"] == "Name"), "-")

def attached_to(a):
    if a.get("InstanceId"):
        return a["InstanceId"]
    if a.get("NetworkInterfaceId"):
        return a["NetworkInterfaceId"]
    return "(idle)"

fmt = "{:<4} {:<16} {:<26} {:<22} {}"
print(f"Found {len(addresses)} Elastic IP(s) in {region}:\n")
print(fmt.format("#", "PUBLIC IP", "ALLOCATION ID", "ATTACHED TO", "NAME"))
print("-" * 85)
for n, a in enumerate(addresses, 1):
    print(fmt.format(n, a["PublicIp"], a["AllocationId"], attached_to(a), eip_name(a)))

choice = input("\nRelease which? 'all', 'idle' (unattached only), or numbers like 1,3 (Enter = cancel): ").strip().lower()
if not choice:
    raise SystemExit("Cancelled, nothing released.")

if choice == "all":
    selected = addresses
elif choice == "idle":
    selected = [a for a in addresses if not a.get("AssociationId")]
else:
    try:
        idx = {int(x) for x in choice.split(",")}
        selected = [addresses[i - 1] for i in sorted(idx) if 1 <= i <= len(addresses)]
    except ValueError:
        raise SystemExit("Invalid input, nothing released.")

if not selected:
    raise SystemExit("No valid selection, nothing released.")

print(f"\nAbout to PERMANENTLY release {len(selected)} Elastic IP(s) in {region}:")
for a in selected:
    print(f"  {a['PublicIp']}  {a['AllocationId']}  {attached_to(a)}")

in_use = [a for a in selected if a.get("AssociationId")]
if in_use:
    print(f"\nWARNING: {len(in_use)} of these are attached. AWS will refuse to release them "
          "until you disassociate them first.")

print("You cannot get the same IP address back once it is released.")

if input("\nType 'release' to confirm: ").strip() != "release":
    raise SystemExit("Aborted, nothing released.")

for a in selected:
    try:
        ec2.release_address(AllocationId=a["AllocationId"])
        print("Released", a["PublicIp"])
    except ClientError as e:
        print("FAILED  ", a["PublicIp"], "-", e.response["Error"]["Message"])
