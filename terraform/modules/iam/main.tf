# IAM Module for EKS Pod Identity
# This module uses EKS Pod Identity Association instead of IRSA for simpler configuration

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
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::nyc-tlc",
          "arn:aws:s3:::nyc-tlc/*"
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

# IAM Role for Spark Service Account (Pod Identity)
resource "aws_iam_role" "spark_sa" {
  name = "${var.cluster_name}-spark-sa-role"

  # Simplified trust policy for Pod Identity (no OIDC conditions needed)
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
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

# IAM Role for Polars Service Account (Pod Identity)
resource "aws_iam_role" "polars_sa" {
  name = "${var.cluster_name}-polars-sa-role"

  # Simplified trust policy for Pod Identity (no OIDC conditions needed)
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "pods.eks.amazonaws.com"
        }
        Action = [
          "sts:AssumeRole",
          "sts:TagSession"
        ]
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

# EKS Pod Identity Association for Spark
resource "aws_eks_pod_identity_association" "spark" {
  cluster_name    = var.cluster_name
  namespace       = "default"
  service_account = "spark-sa"
  role_arn        = aws_iam_role.spark_sa.arn

  tags = {
    Name        = "${var.cluster_name}-spark-pod-identity"
    Environment = var.environment
  }
}

# EKS Pod Identity Association for Polars
resource "aws_eks_pod_identity_association" "polars" {
  cluster_name    = var.cluster_name
  namespace       = "default"
  service_account = "polars-sa"
  role_arn        = aws_iam_role.polars_sa.arn

  tags = {
    Name        = "${var.cluster_name}-polars-pod-identity"
    Environment = var.environment
  }
}
