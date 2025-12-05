# Main Terraform configuration for ETL Benchmark Infrastructure
terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "etl-benchmark"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# Get available AZs
data "aws_availability_zones" "available" {
  state = "available"
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  cluster_name = var.cluster_name
  vpc_cidr     = var.vpc_cidr
  azs          = slice(data.aws_availability_zones.available.names, 0, 3)
  environment  = var.environment
}

# EKS Module
module "eks" {
  source = "./modules/eks"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnet_ids
  environment     = var.environment

  # Node group configurations
  node_arch = var.node_arch
  spark_workers_config  = var.spark_workers_config
  polars_workers_config = var.polars_workers_config
}

# S3 Module
module "s3" {
  source = "./modules/s3"

  bucket_name = "etl-benchmark-data-${data.aws_caller_identity.current.account_id}"
  environment = var.environment
}

# ECR Module
module "ecr" {
  source = "./modules/ecr"

  repositories = ["spark-etl", "polars-etl"]
  environment  = var.environment
}

# IAM Module
module "iam" {
  source = "./modules/iam"

  cluster_name       = var.cluster_name
  s3_bucket_arn      = module.s3.bucket_arn
  eks_oidc_provider  = module.eks.oidc_provider_arn
  eks_oidc_issuer    = module.eks.oidc_issuer
  environment        = var.environment
}
