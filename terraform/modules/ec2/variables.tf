# Variables for EC2 Module

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = "etl-benchmark"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "VPC ID where EC2 instance will be created"
  type        = string
}

variable "subnet_id" {
  description = "Subnet ID for EC2 instance (should be public subnet for SSH access)"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type (r6i.2xlarge, r6i.4xlarge, r7g.2xlarge)"
  type        = string
  default     = "r6i.2xlarge"

  validation {
    condition = contains([
      "r6i.2xlarge",  # 8 vCPU, 64GB RAM, x86
      "r6i.4xlarge",  # 16 vCPU, 128GB RAM, x86
      "r6i.8xlarge",  # 32 vCPU, 256GB RAM, x86
      "r7g.2xlarge",  # 8 vCPU, 64GB RAM, Graviton3
      "r7g.4xlarge",  # 16 vCPU, 128GB RAM, Graviton3
      "r7g.8xlarge"   # 32 vCPU, 256GB RAM, Graviton3
    ], var.instance_type)
    error_message = "Instance type must be one of: r6i.2xlarge, r6i.4xlarge, r6i.8xlarge, r7g.2xlarge, r7g.4xlarge, r7g.8xlarge"
  }
}

variable "architecture" {
  description = "CPU architecture (x86_64 or arm64)"
  type        = string
  default     = "x86_64"

  validation {
    condition     = contains(["x86_64", "arm64"], var.architecture)
    error_message = "Architecture must be either x86_64 or arm64"
  }
}

variable "key_name" {
  description = "SSH key pair name for EC2 instance access"
  type        = string
  default     = null
}

variable "ssh_cidr_blocks" {
  description = "CIDR blocks allowed to SSH to the instance"
  type        = list(string)
  default     = ["0.0.0.0/0"] # Restrict this in production!
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket for benchmark data"
  type        = string
}

variable "s3_bucket_name" {
  description = "Name of the S3 bucket for benchmark data"
  type        = string
}

variable "root_volume_size" {
  description = "Size of root volume in GB"
  type        = number
  default     = 100
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "create_instance" {
  description = "Whether to create the EC2 instance"
  type        = bool
  default     = true
}

variable "allocate_eip" {
  description = "Whether to allocate an Elastic IP"
  type        = bool
  default     = false
}

variable "git_repo_url" {
  description = "Git repository URL to clone"
  type        = string
  default     = "https://github.com/yourusername/etl-benchmark.git"
}

variable "git_branch" {
  description = "Git branch to checkout"
  type        = string
  default     = "main"
}
