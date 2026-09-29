import boto3
from aws_region import get_region

region = get_region()
ec2 = boto3.client("ec2", region_name=region)

# Map instance ID -> Name tag
names = {}
for r in ec2.describe_instances()["Reservations"]:
    for i in r["Instances"]:
        names[i["InstanceId"]] = next(
            (t["Value"] for t in i.get("Tags", []) if t["Key"] == "Name"), "-"
        )

fmt = "{:<23} {:>7} {:<6} {:<12} {:<21} {}"
header = fmt.format("VOLUME ID", "SIZE", "TYPE", "STATE", "INSTANCE ID", "INSTANCE NAME")
print(header)
print("-" * (len(header) + 12))

for v in ec2.describe_volumes()["Volumes"]:
    size = f"{v['Size']} GB"
    if not v["Attachments"]:
        # Orphaned volume, not attached to anything
        print(fmt.format(v["VolumeId"], size, v["VolumeType"], v["State"], "(unattached)", "-"))
    for a in v["Attachments"]:
        iid = a["InstanceId"]
        print(fmt.format(v["VolumeId"], size, v["VolumeType"], v["State"], iid, names.get(iid, "?")))
