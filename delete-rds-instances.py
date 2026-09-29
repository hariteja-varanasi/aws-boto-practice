import time
import boto3
from botocore.exceptions import ClientError
from aws_region import get_region

region = get_region()
rds = boto3.client("rds", region_name=region)

dbs = []
for page in rds.get_paginator("describe_db_instances").paginate():
    dbs.extend(page["DBInstances"])

if not dbs:
    raise SystemExit(f"No RDS instances found in {region}.")

fmt = "{:<4} {:<26} {:<14} {:<12} {:<11} {:>7} {:<5} {}"
print(f"Found {len(dbs)} RDS instance(s) in {region}:\n")
print(fmt.format("#", "IDENTIFIER", "CLASS", "ENGINE", "STATUS", "STORAGE", "PROT", "CLUSTER"))
print("-" * 105)
for n, d in enumerate(dbs, 1):
    print(fmt.format(n, d["DBInstanceIdentifier"], d["DBInstanceClass"], d["Engine"],
                     d["DBInstanceStatus"], f"{d['AllocatedStorage']} GB",
                     "yes" if d.get("DeletionProtection") else "no",
                     d.get("DBClusterIdentifier", "-")))

choice = input("\nDelete which? 'all' or numbers like 1,3 (Enter = cancel): ").strip().lower()
if not choice:
    raise SystemExit("Cancelled, nothing deleted.")
if choice == "all":
    selected = dbs
else:
    try:
        idx = {int(x) for x in choice.split(",")}
        selected = [dbs[i - 1] for i in sorted(idx) if 1 <= i <= len(dbs)]
    except ValueError:
        raise SystemExit("Invalid input, nothing deleted.")
if not selected:
    raise SystemExit("No valid selection, nothing deleted.")

print(f"\nAbout to PERMANENTLY delete {len(selected)} database instance(s) in {region}:")
for d in selected:
    print(f"  {d['DBInstanceIdentifier']}  ({d['Engine']}, {d['AllocatedStorage']} GB)")

if input("\nType 'delete' to confirm: ").strip() != "delete":
    raise SystemExit("Aborted, nothing deleted.")

take_snap = input("Take a final snapshot before deleting? (yes/no): ").strip().lower() == "yes"

protected = [d for d in selected if d.get("DeletionProtection") and not d.get("DBClusterIdentifier")]
if protected:
    print("\nDeletion protection is on for:", ", ".join(d["DBInstanceIdentifier"] for d in protected))
    if input("Type 'disable' to turn it off for them (anything else skips them): ").strip() == "disable":
        for d in protected:
            try:
                rds.modify_db_instance(DBInstanceIdentifier=d["DBInstanceIdentifier"],
                                       DeletionProtection=False, ApplyImmediately=True)
                d["DeletionProtection"] = False
                print("Protection disabled for", d["DBInstanceIdentifier"])
            except ClientError as e:
                print("FAILED to disable protection for", d["DBInstanceIdentifier"], "-", e.response["Error"]["Message"])

stamp = time.strftime("%Y%m%d-%H%M")
for d in selected:
    ident = d["DBInstanceIdentifier"]
    if d.get("DBClusterIdentifier"):
        print("Skipped ", ident, "(part of an Aurora/Multi-AZ cluster; delete the cluster instead)")
        continue
    if d.get("DeletionProtection"):
        print("Skipped ", ident, "(deletion protection still on)")
        continue
    kwargs = {"DBInstanceIdentifier": ident, "DeleteAutomatedBackups": True}
    if take_snap:
        kwargs.update(SkipFinalSnapshot=False, FinalDBSnapshotIdentifier=f"{ident}-final-{stamp}")
    else:
        kwargs["SkipFinalSnapshot"] = True
    try:
        rds.delete_db_instance(**kwargs)
        print("Deleting", ident)
    except ClientError as e:
        print("FAILED  ", ident, "-", e.response["Error"]["Message"])
