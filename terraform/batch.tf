# AWS Batch Infrastructure for Polars + DuckDB TPC-H ETL
# This configuration integrates with the existing EKS infrastructure
# to provide a Fargate-based alternative for single-node workloads

# IAM Role for Batch Job Execution (Fargate)
resource "aws_iam_role" "batch_execution_role" {
  name = "${var.cluster_name}-batch-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.cluster_name}-batch-execution-role"
  }
}

resource "aws_iam_role_policy_attachment" "batch_execution_role_policy" {
  role       = aws_iam_role.batch_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM Role for Batch Job (Application)
resource "aws_iam_role" "batch_job_role" {
  name = "${var.cluster_name}-batch-job-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.cluster_name}-batch-job-role"
  }
}

# IAM Policy for S3 Access
resource "aws_iam_role_policy" "batch_job_s3_policy" {
  name = "${var.cluster_name}-batch-job-s3-policy"
  role = aws_iam_role.batch_job_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          module.s3.bucket_arn,
          "${module.s3.bucket_arn}/*"
        ]
      }
    ]
  })
}

# CloudWatch Logs Group
resource "aws_cloudwatch_log_group" "batch_logs" {
  name              = "/aws/batch/${var.cluster_name}-polars-tpch"
  retention_in_days = 7

  tags = {
    Name = "${var.cluster_name}-batch-logs"
  }
}

# Batch Compute Environment (Fargate)
resource "aws_batch_compute_environment" "polars_fargate" {
  compute_environment_name = "${var.cluster_name}-polars-fargate"
  type                     = "MANAGED"

  compute_resources {
    type      = "FARGATE"
    max_vcpus = 256

    subnets = module.vpc.private_subnet_ids

    security_group_ids = [aws_security_group.batch_sg.id]
  }

  service_role = aws_iam_role.batch_service_role.arn

  depends_on = [aws_iam_role_policy_attachment.batch_service_role_policy]
}

# Security Group for Batch
resource "aws_security_group" "batch_sg" {
  name        = "${var.cluster_name}-batch-sg"
  description = "Security group for Batch compute environment"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.cluster_name}-batch-sg"
  }
}

# IAM Role for Batch Service
resource "aws_iam_role" "batch_service_role" {
  name = "${var.cluster_name}-batch-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "batch.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.cluster_name}-batch-service-role"
  }
}

resource "aws_iam_role_policy_attachment" "batch_service_role_policy" {
  role       = aws_iam_role.batch_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}

# Batch Job Queue
resource "aws_batch_job_queue" "polars_queue" {
  name     = "${var.cluster_name}-polars-queue"
  state    = "ENABLED"
  priority = 1

  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.polars_fargate.arn
  }

  tags = {
    Name = "${var.cluster_name}-polars-queue"
  }
}

# Batch Job Definition
resource "aws_batch_job_definition" "polars_tpch" {
  name = "${var.cluster_name}-polars-tpch"
  type = "container"

  platform_capabilities = ["FARGATE"]

  container_properties = jsonencode({
    image = "${module.ecr.repository_urls["polars-etl"]}:latest"

    jobRoleArn       = aws_iam_role.batch_job_role.arn
    executionRoleArn = aws_iam_role.batch_execution_role.arn

    resourceRequirements = [
      {
        type  = "VCPU"
        value = "4"
      },
      {
        type  = "MEMORY"
        value = "16384"
      }
    ]

    environment = [
      {
        name  = "AWS_REGION"
        value = var.aws_region
      },
      {
        name  = "PYTHONUNBUFFERED"
        value = "1"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.batch_logs.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "polars-tpch"
      }
    }

    fargatePlatformConfiguration = {
      platformVersion = "LATEST"
    }

    networkConfiguration = {
      assignPublicIp = "ENABLED"
    }
  })

  retry_strategy {
    attempts = 2

    evaluate_on_exit {
      action           = "RETRY"
      on_status_reason = "Task failed to start"
    }

    evaluate_on_exit {
      action           = "EXIT"
      on_status_reason = "*"
    }
  }

  timeout {
    attempt_duration_seconds = 3600
  }

  tags = {
    Name = "${var.cluster_name}-polars-tpch"
  }
}
