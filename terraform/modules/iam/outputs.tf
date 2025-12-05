output "spark_service_account_role_arn" {
  description = "ARN of the IAM role for Spark service account"
  value       = aws_iam_role.spark_sa.arn
}

output "polars_service_account_role_arn" {
  description = "ARN of the IAM role for Polars service account"
  value       = aws_iam_role.polars_sa.arn
}

output "s3_access_policy_arn" {
  description = "ARN of the S3 access policy"
  value       = aws_iam_policy.s3_access.arn
}

output "cloudwatch_logs_policy_arn" {
  description = "ARN of the CloudWatch Logs policy"
  value       = aws_iam_policy.cloudwatch_logs.arn
}
