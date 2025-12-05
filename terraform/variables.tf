# Variables for ETL Benchmark Infrastructure

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
  default     = "etl-benchmark-cluster"
}

variable "cluster_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "spark_workers_config" {
  description = "Configuration for Spark worker node group"
  type = object({
    instance_type = string
    min_size      = number
    max_size      = number
    desired_size  = number
  })
  default = {
    instance_type = "m7g.large"
    min_size      = 2
    max_size      = 10
    desired_size  = 2
  }
}

variable "polars_workers_config" {
  description = "Configuration for Polars worker node group"
  type = object({
    instance_type = string
    min_size      = number
    max_size      = number
    desired_size  = number
  })
  default = {
    instance_type = "m7g.large"
    min_size      = 0
    max_size      = 2
    desired_size  = 0
  }
}

variable "node_arch" {
  description = "CPU architecture for EKS nodes: x86 or arm"
  type        = string
  default     = "arm"
}

# EC2 Variables for Polars

variable "ec2_create_instance" {
  description = "Whether to create the EC2 instance for Polars"
  type        = bool
  default     = false
}

variable "ec2_instance_type" {
  description = "EC2 instance type for Polars (r6i.2xlarge, r6i.4xlarge, r7g.2xlarge)"
  type        = string
  default     = "r6i.2xlarge"
}

variable "ec2_architecture" {
  description = "CPU architecture for EC2 instance (x86_64 or arm64)"
  type        = string
  default     = "x86_64"
}

variable "ec2_key_name" {
  description = "SSH key pair name for EC2 instance"
  type        = string
  default     = null
}

variable "ec2_ssh_cidr_blocks" {
  description = "CIDR blocks allowed to SSH to EC2 instance"
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "ec2_allocate_eip" {
  description = "Whether to allocate an Elastic IP for EC2 instance"
  type        = bool
  default     = false
}

variable "git_repo_url" {
  description = "Git repository URL to clone on EC2 instance"
  type        = string
  default     = "https://github.com/yourusername/etl-benchmark.git"
}

variable "git_branch" {
  description = "Git branch to checkout"
  type        = string
  default     = "main"
}
