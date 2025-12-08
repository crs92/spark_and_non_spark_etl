# EC2 Module for Polars ETL Benchmark
# This module creates a single EC2 instance for vertical scaling comparison

# Get latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*"]
  }

  filter {
    name   = "architecture"
    values = [var.architecture]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Security Group for EC2 instance
resource "aws_security_group" "polars_ec2" {
  name_prefix = "${var.name_prefix}-polars-ec2-"
  description = "Security group for Polars ETL EC2 instance"
  vpc_id      = var.vpc_id

  # SSH access (restrict to your IP in production)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_cidr_blocks
    description = "SSH access"
  }

  # Outbound internet access
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name        = "${var.name_prefix}-polars-ec2-sg"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

# IAM Role for EC2 instance
resource "aws_iam_role" "polars_ec2" {
  name_prefix = "${var.name_prefix}-polars-ec2-"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.name_prefix}-polars-ec2-role"
    Environment = var.environment
  }
}

# IAM Policy for S3 access
resource "aws_iam_role_policy" "polars_s3_access" {
  name_prefix = "s3-access-"
  role        = aws_iam_role.polars_ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
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
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::ccorsetti",
          "arn:aws:s3:::ccorsetti/*"
        ]
      }
    ]
  })
}

# IAM Policy for CloudWatch
resource "aws_iam_role_policy" "polars_cloudwatch" {
  name_prefix = "cloudwatch-"
  role        = aws_iam_role.polars_ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "ec2:DescribeVolumes",
          "ec2:DescribeTags",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
          "logs:DescribeLogGroups",
          "logs:CreateLogStream",
          "logs:CreateLogGroup"
        ]
        Resource = "*"
      }
    ]
  })
}

# Attach SSM policy for Systems Manager access (optional but useful)
resource "aws_iam_role_policy_attachment" "polars_ssm" {
  role       = aws_iam_role.polars_ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# IAM Policy for ECR access (to pull and push Docker images)
resource "aws_iam_role_policy" "polars_ecr_access" {
  name_prefix = "ecr-access-"
  role        = aws_iam_role.polars_ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM Instance Profile
resource "aws_iam_instance_profile" "polars_ec2" {
  name_prefix = "${var.name_prefix}-polars-ec2-"
  role        = aws_iam_role.polars_ec2.name

  tags = {
    Name        = "${var.name_prefix}-polars-ec2-profile"
    Environment = var.environment
  }
}

# CloudWatch Log Group for ETL logs
resource "aws_cloudwatch_log_group" "polars_etl" {
  name              = "/aws/ec2/${var.name_prefix}-polars-etl"
  retention_in_days = var.log_retention_days

  tags = {
    Name        = "${var.name_prefix}-polars-etl-logs"
    Environment = var.environment
  }
}

# User data script for instance initialization
locals {
  user_data = templatefile("${path.module}/user_data.sh", {
    cloudwatch_log_group = aws_cloudwatch_log_group.polars_etl.name
    aws_region           = var.aws_region
    s3_bucket_name       = var.s3_bucket_name
    git_repo_url         = var.git_repo_url
    git_branch           = var.git_branch
  })
}

# EC2 Instance
resource "aws_instance" "polars_etl" {
  count = var.create_instance ? 1 : 0

  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [aws_security_group.polars_ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.polars_ec2.name
  key_name               = var.key_name

  user_data                   = local.user_data
  user_data_replace_on_change = true

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size
    delete_on_termination = true
    encrypted             = true

    tags = {
      Name = "${var.name_prefix}-polars-root"
    }
  }

  # Enable detailed monitoring for better CloudWatch metrics
  monitoring = true

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
    instance_metadata_tags      = "enabled"
  }

  tags = {
    Name         = "${var.name_prefix}-polars-etl"
    Environment  = var.environment
    Purpose      = "polars-etl-benchmark"
    InstanceType = var.instance_type
  }

  lifecycle {
    ignore_changes = [ami]
  }
}

# Elastic IP (optional, for stable SSH access)
resource "aws_eip" "polars_etl" {
  count = var.create_instance && var.allocate_eip ? 1 : 0

  instance = aws_instance.polars_etl[0].id
  domain   = "vpc"

  tags = {
    Name        = "${var.name_prefix}-polars-etl-eip"
    Environment = var.environment
  }
}
