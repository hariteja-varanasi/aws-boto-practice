import boto3

s3 = boto3.client("s3")
print("Buckets:", [b["Name"] for b in s3.list_buckets()["Buckets"]])

ec2 = boto3.client("ec2")  # uses us-east-1 from your config
for r in ec2.describe_instances()["Reservations"]:
    for i in r["Instances"]:
        print(i["InstanceId"], i["State"]["Name"])