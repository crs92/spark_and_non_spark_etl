# Outputs for ETL Benchmark Infrastructure

output "cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "Endpoint for EKS cluster"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ID for EKS cluster"
  value       = module.eks.cluster_security_group_id
}

# output "cluster_oidc_issuer" {
#   description = "OIDC issuer URL for the EKS cluster"
#   value       = module.eks.oidc_issuer
# }

output "s3_bucket_name" {
  description = "Name of the S3 bucket for benchmark data"
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.s3.bucket_arn
}

output "ecr_repository_urls" {
  description = "URLs of ECR repositories"
  value       = module.ecr.repository_urls
}

output "spark_service_account_role_arn" {
  description = "IAM role ARN for Spark service account"
  value       = module.iam.spark_service_account_role_arn
}

output "polars_service_account_role_arn" {
  description = "IAM role ARN for Polars service account"
  value       = module.iam.polars_service_account_role_arn
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "IDs of private subnets"
  value       = module.vpc.private_subnet_ids
}

output "configure_kubectl" {
  description = "Command to configure kubectl"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

# EC2 Outputs

output "ec2_instance_id" {
  description = "ID of the Polars EC2 instance"
  value       = module.ec2.instance_id
}

output "ec2_instance_public_ip" {
  description = "Public IP of the Polars EC2 instance"
  value       = module.ec2.instance_public_ip
}

output "ec2_instance_private_ip" {
  description = "Private IP of the Polars EC2 instance"
  value       = module.ec2.instance_private_ip
}

output "ec2_ssh_command" {
  description = "SSH command to connect to Polars EC2 instance"
  value       = module.ec2.ssh_command
}

output "ec2_cloudwatch_log_group" {
  description = "CloudWatch log group for Polars EC2 instance"
  value       = module.ec2.cloudwatch_log_group
}

output "ec2_iam_role_arn" {
  description = "IAM role ARN for Polars EC2 instance"
  value       = module.ec2.iam_role_arn
}
