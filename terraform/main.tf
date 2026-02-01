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
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
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

data "aws_eks_cluster" "cluster" {
  name = module.eks.cluster_id
}

data "aws_eks_cluster_auth" "cluster" {
  name = module.eks.cluster_id
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.cluster.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.cluster.token
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.cluster.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.cluster.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.cluster.token
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
  node_arch             = var.node_arch
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

  repositories = ["spark-etl", "polars-etl", "polars-tpch-etl"]
  environment  = var.environment
}

# IAM Module (using Pod Identity instead of IRSA)
module "iam" {
  source = "./modules/iam"

  cluster_name  = var.cluster_name
  s3_bucket_arn = module.s3.bucket_arn
  environment   = var.environment

  # Pod Identity requires the EKS cluster to exist first
  depends_on = [module.eks]
}

# EC2 Module for Polars (Vertical Scaling)
module "ec2" {
  source = "./modules/ec2"

  name_prefix     = var.cluster_name
  environment     = var.environment
  aws_region      = var.aws_region
  vpc_id          = module.vpc.vpc_id
  subnet_id       = module.vpc.public_subnet_ids[0]
  instance_type   = var.ec2_instance_type
  architecture    = var.ec2_architecture
  key_name        = var.ec2_key_name
  ssh_cidr_blocks = var.ec2_ssh_cidr_blocks
  s3_bucket_arn   = module.s3.bucket_arn
  s3_bucket_name  = module.s3.bucket_name
  create_instance = var.ec2_create_instance
  allocate_eip    = var.ec2_allocate_eip
  git_repo_url    = var.git_repo_url
  git_branch      = var.git_branch
}
