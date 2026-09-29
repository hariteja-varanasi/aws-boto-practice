# AWS Boto Practice: Cleanup Scripts

Interactive boto3 scripts for listing and deleting AWS resources. Each script lists the resources first, lets you pick `all` or specific row numbers, shows a summary, and only acts after you type a confirmation word.

## Setup

Tested on Kali Linux (x86_64).

### 1. Install the AWS CLI v2

```bash
cd /tmp
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip
sudo ./aws/install
aws --version
```

For ARM machines, use `awscli-exe-linux-aarch64.zip` in the URL instead.

To upgrade an existing install later, download a fresh zip and re-run the installer with the update flag:

```bash
cd /tmp
rm -rf aws awscliv2.zip
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip
sudo ./aws/install --update
aws --version
```

Your credentials in `~/.aws/` are not touched by an upgrade.

### 2. Configure credentials

```bash
aws configure
```

You'll be asked for four values: Access Key ID, Secret Access Key, default region (e.g. `us-east-1`), and output format (`json`). Create the access key in the AWS console under IAM, Users, your user, Security credentials, Create access key.

Verify that it works:

```bash
aws sts get-caller-identity
```

Never commit `~/.aws/credentials` or paste your secret key anywhere public. Use an IAM user with least-privilege permissions rather than root keys.

### 3. Create a Python virtual environment

Recent Kali versions block system-wide `pip install` (PEP 668), so use a venv:

```bash
sudo apt install python3-venv
python3 -m venv ~/aws-env
source ~/aws-env/bin/activate
```

Your prompt should now start with `(aws-env)`. Run `source ~/aws-env/bin/activate` again in every new terminal before running the scripts.

### 4. Install boto3

```bash
pip install boto3
```

Test it:

```bash
python3 -c "import boto3; print(boto3.client('sts').get_caller_identity())"
```

boto3 reads the credentials from `~/.aws/` automatically, so no keys are needed in the code.

## Scripts

| Component | Script |
|---|---|
| Auto Scaling groups | `delete-auto-scaling-groups.py` |
| EC2 instances | `delete-ec2-instances.py` |
| Load balancers | `delete-load-balancers.py` |
| NAT gateways | `delete-nat-gateways.py` |
| VPC interface endpoints | `delete-vpc-endpoints.py` |
| RDS instances | `delete-rds-instances.py` |
| EBS volumes | `delete-ebs-volumes.py` |
| EBS snapshots | `delete-ebs-snapshots.py` |
| Elastic IPs | `release-elastic-ips.py` |

Related scripts:

- `aws_region.py` is the shared region prompt imported by the scripts below. Keep it in the same folder.
- `delete-target-groups.py` cleans up load balancer target groups (run it after `delete-load-balancers.py`).
- `aws-region-sweep.py` is a read-only scan of every region for the resource types above.
- `aws-hanging-volumes.py` lists EBS volumes with their attached instances.
- `instance-to-keep.py` is the "delete everything except this one instance" variant.

## Notes

### Deletion order

Dependencies matter, so run them in this order:

1. Auto Scaling groups (otherwise they relaunch what you delete)
2. EC2 instances, load balancers, NAT gateways, VPC endpoints, RDS
3. EBS volumes (wait for the instances to finish terminating, then use the `available` option)
4. Snapshots
5. Elastic IPs last, since load balancers and NAT gateways hold them until they're gone

The script for each step:

| Step | Script(s) |
|---|---|
| 1. Auto Scaling groups | `delete-auto-scaling-groups.py` |
| 2. EC2, load balancers, NAT gateways, VPC endpoints, RDS | `delete-ec2-instances.py`, `delete-load-balancers.py`, `delete-nat-gateways.py`, `delete-vpc-endpoints.py`, `delete-rds-instances.py` |
| 3. EBS volumes | `delete-ebs-volumes.py` |
| 4. Snapshots | `delete-ebs-snapshots.py` |
| 5. Elastic IPs | `release-elastic-ips.py` |

Target groups have no step of their own. Run `delete-target-groups.py` after the load balancers are gone.

### Region

Every script asks which region to use when it starts:

```
AWS region (Enter = us-east-1):
```

Press Enter to use your default region from `aws configure`, or type one such as `ap-south-1`. You can also pass it as the first argument and skip the prompt:

```bash
python delete-rds-instances.py ap-south-1
```

The prompt lives in the shared helper `aws_region.py`, so keep it in the same folder as the scripts. An unrecognised region name is rejected and you're asked again. Regions that are opt-in (for example `ap-east-1`) must be enabled on your account first, otherwise calls fail with an authentication error.

`aws-region-sweep.py` doesn't ask, because it scans every region.

### Keep `nexops-practice-server`

If you don't want to lose it, don't pick `all` in `delete-ec2-instances.py` or `delete-ebs-volumes.py`. Use the row numbers, and check the NAME column before you confirm. (`instance-to-keep.py` is the "delete everything except this one" variant.)

### RDS and Aurora

The RDS script skips instances that belong to a cluster (Aurora), because those are deleted at the cluster level. If the sweep finds one, a cluster version of the script is needed.

### Permissions

`aws_user_zero` needs the matching `Describe*` and `Delete*`/`Terminate*` actions for each service. An `UnauthorizedOperation` or `AccessDenied` error in the FAILED lines means a missing permission, not a bug.
