variable "cluster_name" {
  description = "Name of the EKS cluster"
  type        = string
}

variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket for ETL data"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}
