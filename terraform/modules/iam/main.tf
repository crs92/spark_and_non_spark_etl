# IAM Module for EKS Service Accounts

# Extract OIDC provider ID from ARN
locals {
  oidc_provider_id = replace(var.eks_oidc_issuer, "https://", "")
}

# S3 Access Policy for ETL workloads
resource "aws_iam_policy" "s3_access" {
  name        = "${var.cluster_name}-s3-access"
  description = "Policy for S3 access from EKS pods"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets",
          "s3:GetBucketLocation"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Role for Spark Service Account
resource "aws_iam_role" "spark_sa" {
  name = "${var.cluster_name}-spark-sa-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.eks_oidc_provider
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${local.oidc_provider_id}:sub" = "system:serviceaccount:default:spark-sa"
            "${local.oidc_provider_id}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "${var.cluster_name}-spark-sa-role"
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "spark_sa_s3" {
  role       = aws_iam_role.spark_sa.name
  policy_arn = aws_iam_policy.s3_access.arn
}

# IAM Role for Polars Service Account
resource "aws_iam_role" "polars_sa" {
  name = "${var.cluster_name}-polars-sa-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = var.eks_oidc_provider
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "${local.oidc_provider_id}:sub" = "system:serviceaccount:default:polars-sa"
            "${local.oidc_provider_id}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = {
    Name        = "${var.cluster_name}-polars-sa-role"
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "polars_sa_s3" {
  role       = aws_iam_role.polars_sa.name
  policy_arn = aws_iam_policy.s3_access.arn
}

# Additional CloudWatch Logs policy for monitoring
resource "aws_iam_policy" "cloudwatch_logs" {
  name        = "${var.cluster_name}-cloudwatch-logs"
  description = "Policy for CloudWatch Logs access from EKS pods"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "spark_sa_logs" {
  role       = aws_iam_role.spark_sa.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}

resource "aws_iam_role_policy_attachment" "polars_sa_logs" {
  role       = aws_iam_role.polars_sa.name
  policy_arn = aws_iam_policy.cloudwatch_logs.arn
}
