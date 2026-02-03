# ETL Benchmark Infrastructure Configuration
# This file contains the actual values used for deployment

# AWS Configuration
aws_region = "eu-central-1"
environment = "dev"

# EKS Cluster Configuration
cluster_name = "etl-benchmark-cluster"
cluster_version = "1.29"  # Updated to match current cluster version

# VPC Configuration
vpc_cidr = "10.0.0.0/16"

# Spark Worker Node Group Configuration
# Upgraded to m6i.2xlarge for better Spark performance with larger datasets
spark_workers_config = {
  instance_type = "m6i.2xlarge"  # 8 vCPUs, 32GB RAM (better for Spark SF=100)
  min_size      = 2
  max_size      = 12             # Allow scaling for large workloads
  desired_size  = 3              # Start with 3 nodes for better capacity
}

# Polars Worker Node Group Configuration (not used - using AWS Batch instead)
polars_workers_config = {
  instance_type = "m5.large"
  min_size      = 0
  max_size      = 2
  desired_size  = 0
}

# Node Architecture
node_arch = "x86"

# EC2 Configuration (for data generation)
ec2_create_instance = false
ec2_instance_type = "r6i.2xlarge"
ec2_architecture = "x86_64"
ec2_allocate_eip = false
ec2_ssh_cidr_blocks = ["0.0.0.0/0"]

# Git Configuration (for EC2 user data)
git_repo_url = "https://github.com/yourusername/etl-benchmark.git"
git_branch = "main"
