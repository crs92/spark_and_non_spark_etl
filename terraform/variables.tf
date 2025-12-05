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
