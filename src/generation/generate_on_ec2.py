#!/usr/bin/env python3
import argparse
import json
import os
import time

import boto3
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Generate TPC-H data on EC2")
    parser.add_argument("--scale-factor", type=int, required=True)
    parser.add_argument("--region", default="eu-central-1")
    parser.add_argument("--bucket", help="S3 bucket")
    args = parser.parse_args()

    bucket = args.bucket or os.getenv("S3_BUCKET_NAME")
    sf = args.scale_factor
    prefix = f"tpch-sf{sf}"

    ec2 = boto3.client("ec2", region_name=args.region)
    iam = boto3.client("iam")
    ssm = boto3.client("ssm", region_name=args.region)

    role_name = "TPCH-Generator-Role"
    try:
        assume_role_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole",
            }],
        }
        iam.create_role(
            RoleName=role_name, AssumeRolePolicyDocument=json.dumps(assume_role_policy)
        )
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn="arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
        )
        iam.attach_role_policy(
            RoleName=role_name, PolicyArn="arn:aws:iam::aws:policy/AmazonS3FullAccess"
        )
        iam.create_instance_profile(InstanceProfileName=role_name)
        iam.add_role_to_instance_profile(
            InstanceProfileName=role_name, RoleName=role_name
        )
        time.sleep(10)
    except Exception:  # noqa: S110
        # Role may already exist, continue
        pass

    print(f"🚀 Launching C6i.2xlarge for SF{sf}...")
    ami_id = ec2.describe_images(
        Owners=["amazon"],
        Filters=[{"Name": "name", "Values": ["al2023-ami-2023.*-x86_64"]}],
    )["Images"][0]["ImageId"]

    instance = ec2.run_instances(
        ImageId=ami_id,
        InstanceType="c6i.2xlarge",
        MinCount=1,
        MaxCount=1,
        IamInstanceProfile={"Name": role_name},
        BlockDeviceMappings=[{
            "DeviceName": "/dev/xvda",
            "Ebs": {
                "VolumeSize": (
                    200
                ),  # Increased to 200GB to prevent "No space left on device"
                "VolumeType": "gp3",
            },
        }],
    )["Instances"][0]
    instance_id = instance["InstanceId"]

    ec2.get_waiter("instance_running").wait(InstanceIds=[instance_id])

    print("⏳ Waiting for SSM Agent...")
    for _ in range(30):
        if ssm.describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        ).get("InstanceInformationList"):
            print("✅ SSM Agent Online.")
            break
        time.sleep(10)

    # Finalized Command Block
    generation_script = f"""#!/bin/bash
    set -e
    export HOME=/root
    export PATH=$PATH:/root/.cargo/bin

    # 1. Ensure the OS sees the full 200GB EBS volume
    # (Sometimes the partition doesn't auto-expand immediately)
    sudo growpart /dev/xvda 1 || true
    sudo xfs_growfs / || true

    # 2. Setup Environment
    sudo yum install -y gcc
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source /root/.cargo/env

    # 3. Install Tool
    cargo install tpchgen-cli

    # 4. CLEANUP RUST CACHE (Essential to save disk/RAM)
    rm -rf /root/.cargo/registry
    rm -rf /root/.cargo/git

    # 5. GENERATE DATA ON EBS VOLUME (NOT /tmp/)
    # We use /root/tpch_data to ensure we use the 200GB EBS disk
    mkdir -p /root/tpch_data
    tpchgen-cli --scale-factor {sf} --format parquet --output-dir /root/tpch_data

    # 6. S3 Upload
    aws s3 sync /root/tpch_data s3://{bucket}/{prefix}/
    echo "Success" | aws s3 cp - s3://{bucket}/{prefix}/_SUCCESS

    # Optional: cleanup local data to be clean
    rm -rf /root/tpch_data
    """

    print("🛠️  Running Generation (this involves Rust compilation, wait ~4-5 mins)...")
    cmd = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [generation_script]},
    )
    command_id = cmd["Command"]["CommandId"]

    while True:
        try:
            res = ssm.get_command_invocation(
                CommandId=command_id, InstanceId=instance_id
            )
            status = res["Status"]
            print(f"Status: {status}")
            if status in ["Success", "Failed", "TimedOut", "Cancelled"]:
                if status != "Success":
                    print("❌ ERROR OUTPUT:")
                    print(res.get("StandardErrorContent"))
                break
        except Exception:  # noqa: S110
            # Command invocation not ready yet, retry
            pass
        time.sleep(20)

    print("🧹 Cleaning up...")
    ec2.terminate_instances(InstanceIds=[instance_id])
    print(f"✅ Finished! Data is in s3://{bucket}/{prefix}/")


if __name__ == "__main__":
    main()
