import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from concurrent.futures import ThreadPoolExecutor

cfg = Config(retries={"max_attempts": 3, "mode": "standard"},
             connect_timeout=5, read_timeout=20)

def name_tag(tags):
    return next((t["Value"] for t in tags or [] if t["Key"] == "Name"), "-")

def pages(client, op, key, **kw):
    out = []
    for p in client.get_paginator(op).paginate(**kw):
        out.extend(p[key])
    return out

def scan(region):
    s = boto3.Session(region_name=region)
    ec2 = s.client("ec2", config=cfg)
    elbv2 = s.client("elbv2", config=cfg)
    elb = s.client("elb", config=cfg)
    asg = s.client("autoscaling", config=cfg)
    rds = s.client("rds", config=cfg)

    found, errors = {}, []

    def check(label, fn):
        try:
            rows = fn()
        except ClientError as e:
            errors.append(f"{label}: {e.response['Error']['Code']}")
            return
        except Exception as e:
            errors.append(f"{label}: {type(e).__name__}")
            return
        if rows:
            found[label] = rows

    def instances():
        rows = []
        flt = [{"Name": "instance-state-name",
                "Values": ["pending", "running", "stopping", "stopped"]}]
        for r in pages(ec2, "describe_instances", "Reservations", Filters=flt):
            for i in r["Instances"]:
                rows.append(f"{i['InstanceId']}  {i['InstanceType']}  "
                            f"{i['State']['Name']}  {name_tag(i.get('Tags'))}")
        return rows

    def volumes():
        return [f"{v['VolumeId']}  {v['Size']} GB  {v['VolumeType']}  {v['State']}  {name_tag(v.get('Tags'))}"
                for v in pages(ec2, "describe_volumes", "Volumes")]

    def snapshots():
        return [f"{x['SnapshotId']}  {x['VolumeSize']} GB  {name_tag(x.get('Tags'))}"
                for x in pages(ec2, "describe_snapshots", "Snapshots", OwnerIds=["self"])]

    def eips():
        return [f"{a['PublicIp']}  {a['AllocationId']}  "
                f"{a.get('InstanceId') or a.get('NetworkInterfaceId') or '(idle)'}"
                for a in ec2.describe_addresses()["Addresses"]]

    def lbs():
        rows = [f"{l['LoadBalancerName']}  {l['Type']}  {l['State']['Code']}"
                for l in pages(elbv2, "describe_load_balancers", "LoadBalancers")]
        rows += [f"{l['LoadBalancerName']}  classic"
                 for l in pages(elb, "describe_load_balancers", "LoadBalancerDescriptions")]
        return rows

    def nats():
        flt = [{"Name": "state", "Values": ["pending", "available"]}]
        return [f"{n['NatGatewayId']}  {n['VpcId']}  {n['State']}"
                for n in pages(ec2, "describe_nat_gateways", "NatGateways", Filter=flt)]

    def endpoints():
        flt = [{"Name": "vpc-endpoint-type", "Values": ["Interface", "GatewayLoadBalancer"]}]
        return [f"{e['VpcEndpointId']}  {e['ServiceName']}  {e['State']}"
                for e in pages(ec2, "describe_vpc_endpoints", "VpcEndpoints", Filters=flt)]

    def asgs():
        return [f"{g['AutoScalingGroupName']}  min={g['MinSize']} desired={g['DesiredCapacity']} max={g['MaxSize']}"
                for g in pages(asg, "describe_auto_scaling_groups", "AutoScalingGroups")]

    def dbs():
        return [f"{d['DBInstanceIdentifier']}  {d['DBInstanceClass']}  {d['DBInstanceStatus']}"
                for d in pages(rds, "describe_db_instances", "DBInstances")]

    check("EC2 instances", instances)
    check("EBS volumes", volumes)
    check("EBS snapshots", snapshots)
    check("Elastic IPs", eips)
    check("Load balancers", lbs)
    check("NAT gateways", nats)
    check("VPC interface endpoints", endpoints)
    check("Auto Scaling groups", asgs)
    check("RDS instances", dbs)
    return region, found, errors

if __name__ == "__main__":
    regions = sorted(r["RegionName"] for r in
                     boto3.client("ec2", region_name="us-east-1", config=cfg).describe_regions()["Regions"])
    print(f"Scanning {len(regions)} regions...\n")

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(scan, regions))

    total = 0
    clean = []
    for region, found, errors in results:
        if not found and not errors:
            clean.append(region)
            continue
        print(f"=== {region} ===")
        for label, rows in found.items():
            print(f"  {label} ({len(rows)}):")
            for row in rows:
                print(f"      {row}")
            total += len(rows)
        for err in errors:
            print(f"  (could not check) {err}")
        print()

    print(f"Regions with nothing found ({len(clean)}): {', '.join(clean) or '-'}")
    print(f"\nTotal resources found: {total}")