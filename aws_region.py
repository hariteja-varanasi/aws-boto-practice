"""Shared helper: ask the user which AWS region to use.

Usage in a script:
    from aws_region import get_region
    region = get_region()
    ec2 = boto3.client("ec2", region_name=region)

The region can also be passed as the first command-line argument:
    python delete-ebs-volumes.py ap-south-1
"""
import sys
import boto3


def get_region():
    session = boto3.Session()
    default = session.region_name or "us-east-1"
    valid = set(session.get_available_regions("ec2"))

    arg = sys.argv[1].strip() if len(sys.argv) > 1 else None
    while True:
        region = arg or input(f"AWS region (Enter = {default}): ").strip() or default
        arg = None  # only use the command-line value once
        if region in valid:
            print(f"Using region: {region}\n")
            return region
        print(f"'{region}' is not a recognised region. Examples: us-east-1, ap-south-1, eu-west-1")
