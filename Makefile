# Makefile

# Use bash for all commands
SHELL := /bin/bash

# Define the default goal, which will be executed when you just run "make"
.DEFAULT_GOAL := help

# Define the Python interpreter from our virtual environment
PYTHON := .venv/bin/python

# Define Docker/Podman command
# Check if podman-desktop-root connection is available, otherwise use default
DOCKER := $(shell command -v podman 2>/dev/null || command -v docker 2>/dev/null)
PODMAN_CONNECTION := $(shell podman system connection list 2>/dev/null | grep -q podman-desktop-root && echo "--connection podman-desktop-root" || echo "")
DOCKER_CMD := $(DOCKER) $(PODMAN_CONNECTION)

# Define source code directories
SRC_DIR := src
TEST_DIR := tests

# Phony targets are commands that don't represent a file.
# This tells 'make' to always execute the command regardless of whether a file with that name exists.
.PHONY: help install check format test all clean pre-commit-clean \
        generate-data benchmark \
        docker-build docker-build-spark docker-build-pythonic docker-up docker-down \
        docker-run-spark docker-run-pythonic docker-test-quick docker-benchmark \
        docker-logs docker-shell docker-test docker-clean \
        ecr-login ecr-push ecr-push-spark ecr-push-polars ecr-push-all \
        k8s-setup k8s-benchmark k8s-clean \
        tf-init tf-plan tf-apply tf-destroy tf-output tf-validate \
        benchmark-full-run benchmark-nyc-taxi benchmark-verify benchmark-metrics \
        cost-analysis cost-analysis-region cost-test \
        report-generate report-presentation report-all \
        clean-benchmark clean-reports clean-s3 clean-all \
        quickstart-ec2 quickstart-eks quickstart-full \
        workflow-status workflow-costs

# Self-documenting help command. It parses this file to show available commands.
help: ## ✨ Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## 📦 Install all project dependencies from pyproject.toml
	@echo "--- Installing dependencies using uv ---"
	@uv pip install -e .[dev]

.PHONY: pre-commit-clean
pre-commit-clean: ## 🧹 Clean pre-commit cache
	@echo "--- Cleaning pre-commit cache ---"
	@uv run pre-commit clean
	@echo "pre-commit cache cleaned."

.PHONY: check
check: ## Run code quality tools (only on src/)
	@echo "🚀 Linting code: Running pre-commit on src/"
	@git ls-files -- 'src/**/*.py' | xargs uv run pre-commit run --files
	@echo "✅ Code quality checks passed!"

format: ## 🎨 Auto-format code using Black and Ruff
	@echo "--- Formatting with Black ---"
	@black $(SRC_DIR) $(TEST_DIR)
	@echo "--- Formatting with Ruff Formatter ---"
	@ruff format $(SRC_DIR) $(TEST_DIR)
	@echo "--- Running Ruff linter with auto-fix ---"
	@ruff check $(SRC_DIR) $(TEST_DIR) --fix
	@echo "Code has been formatted."

test: ## 🧪 Run the test suite with pytest
	@echo "--- Running tests ---"
	@$(PYTHON) -m pytest $(TEST_DIR)

all: check test ## ✅ Run all checks and tests

clean: ## 🧹 Remove temporary Python files and build artifacts
	@echo "--- Cleaning up project ---"
	@find . -type f -name "*.py[co]" -delete
	@find . -type d -name "__pycache__" -exec rm -r {} +
	@find . -type d -name ".pytest_cache" -exec rm -r {} +
	@rm -rf build/ dist/ .egg-info/
	@echo "Cleanup complete."

# Data generation and benchmarking
generate-data: ## 📊 Generate test data (use SIZE=small|medium|large, default: small)
	@echo "--- Generating test data ---"
ifeq (${SIZE},)
	@$(PYTHON) -m src.data_generation.cli small
else
	@$(PYTHON) -m src.data_generation.cli ${SIZE}
endif

generate-data-full: ## 📊 Generate complete bulk + incremental data (use SIZE=small|medium|large, default: small)
	@echo "--- Generating complete bulk + incremental data ---"
ifeq (${SIZE},)
	@$(PYTHON) -m src.data_generation.cli small --days 7 --output data/generated
else
	@$(PYTHON) -m src.data_generation.cli ${SIZE} --days 7 --output data/generated
endif
	@echo "✅ Generated bulk (30 days) + incremental (7 days) data"

benchmark: ## 🏁 Run incremental ETL benchmark
	@echo "--- Running incremental ETL benchmark ---"
	@$(PYTHON) scripts/benchmark_incremental.py --input data/generated/clickstream_data_small_simple.csv
	@echo "Benchmark complete!"

benchmark-full: ## 🏆 Run complete bulk + incremental benchmark for both frameworks (use SIZE=small|medium|large, default: small)
	@echo "--- Running complete ETL benchmark (bulk + incremental) ---"
ifeq (${SIZE},)
	@$(PYTHON) scripts/benchmark_full.py --size small
else
	@$(PYTHON) scripts/benchmark_full.py --size ${SIZE}
endif
	@echo "Complete benchmark finished!"

benchmark-docker: ## 🐳 Run Docker/Podman benchmark (use SIZE=small|medium|large, default: small)
	@echo "--- Running Docker/Podman ETL benchmark ---"
	@DATA_SIZE=${SIZE} bash scripts/benchmark_docker.sh
	@echo "Docker benchmark finished!"

benchmark-comprehensive: ## 📊 Run comprehensive benchmark (small, medium, large with 3 runs each)
	@echo "--- Running comprehensive benchmark ---"
	@python3 scripts/run_comprehensive_benchmark.py

# Docker commands
docker-build: ## 🐳 Build both Docker images (AMD64)
	@echo "--- Building both Docker images for AMD64 ---"
	@$(DOCKER_CMD) build --platform linux/amd64 -f Dockerfile.spark -t spark-etl .
	@$(DOCKER_CMD) build --platform linux/amd64 -f Dockerfile.pythonic -t pythonic-etl .

docker-build-spark: ## ⚡ Build Spark ETL image only (AMD64)
	@echo "--- Building Spark ETL image for AMD64 ---"
	@$(DOCKER_CMD) build --platform linux/amd64 -f Dockerfile.spark -t spark-etl .

docker-build-pythonic: ## 🐍 Build Pythonic ETL image only (AMD64)
	@echo "--- Building Pythonic ETL image for AMD64 ---"
	@$(DOCKER_CMD) build --platform linux/amd64 -f Dockerfile.pythonic -t pythonic-etl .

docker-up: ## 🚀 Start infrastructure services
	@echo "--- Starting infrastructure services ---"
	@$(DOCKER_CMD) compose up -d minio postgres
	@echo "Infrastructure started:"
	@echo "  - MinIO Console: http://localhost:9001"
	@echo "  - PostgreSQL: localhost:5432"

docker-run-spark: ## ⚡ Run Spark ETL (with infrastructure)
	@echo "--- Running Spark ETL ---"
	@$(DOCKER_CMD) compose --profile spark up spark-etl

docker-run-pythonic: ## 🐍 Run Pythonic ETL (with infrastructure)
	@echo "--- Running Pythonic ETL ---"
	@$(DOCKER_CMD) compose --profile pythonic up pythonic-etl

docker-test-quick: ## 🧪 Quick test of both ETL images without infrastructure
	@echo "--- Quick ETL image test ---"
	@echo "Testing Pythonic ETL..."
	@bash scripts/test_pythonic_docker.sh
	@echo "Quick test completed."

docker-test-compose: ## 🧪 Test docker-compose setup with infrastructure
	@echo "--- Testing docker-compose setup ---"
	@bash scripts/test_docker_compose.sh

docker-benchmark: ## 📊 Run performance benchmark comparison
	@echo "--- Running ETL performance benchmark ---"
	@python scripts/benchmark.py --data-size small

docker-down: ## 🛑 Stop all Docker services
	@echo "--- Stopping Docker services ---"
	@$(DOCKER_CMD) compose down

docker-logs: ## 📋 Show logs from all Docker services
	@$(DOCKER_CMD) compose logs -f

docker-shell: ## 🐚 Open a shell in the development container
	@$(DOCKER_CMD) compose --profile dev up -d dev-env
	@$(DOCKER_CMD) compose exec dev-env bash

docker-test: ## 🧪 Run tests inside Docker container
	@echo "--- Running tests in Docker container ---"
	@$(DOCKER_CMD) compose --profile dev up -d dev-env
	@$(DOCKER_CMD) compose exec dev-env python -m pytest tests/

docker-clean: ## 🧽 Remove Docker containers, networks, and volumes
	@echo "--- Cleaning up Docker resources ---"
	@$(DOCKER_CMD) compose down -v --remove-orphans
	@$(DOCKER_CMD) system prune -f

# ECR (Elastic Container Registry) commands
ecr-login: ## 🔐 Authenticate with AWS ECR
	@echo "--- Authenticating with ECR ---"
	@AWS_REGION=$${AWS_REGION:-eu-central-1}; \
	AWS_ACCOUNT_ID=$$(aws sts get-caller-identity --query Account --output text); \
	aws ecr get-login-password --region $$AWS_REGION | \
	$(DOCKER_CMD) login --username AWS --password-stdin $$AWS_ACCOUNT_ID.dkr.ecr.$$AWS_REGION.amazonaws.com
	@echo "✅ Successfully authenticated with ECR"

ecr-push-spark: ## 🚀 Build and push Spark image to ECR (usage: make ecr-push-spark VERSION=v1.0.0)
	@echo "--- Building and pushing Spark image to ECR ---"
	@./scripts/push_to_ecr.sh spark $(or $(VERSION),latest)

ecr-push-polars: ## 🚀 Build and push Polars image to ECR (usage: make ecr-push-polars VERSION=v1.0.0)
	@echo "--- Building and pushing Polars image to ECR ---"
	@./scripts/push_to_ecr.sh polars $(or $(VERSION),latest)

ecr-push-all: ## 🚀 Build and push both images to ECR (usage: make ecr-push-all VERSION=v1.0.0)
	@echo "--- Building and pushing all images to ECR ---"
	@./scripts/push_to_ecr.sh all $(or $(VERSION),latest)

ecr-push: ecr-push-all ## 🚀 Alias for ecr-push-all

# Kubernetes commands
k8s-setup: ## ☸️ Setup Kubernetes cluster for distributed testing
	@echo "--- Setting up Kubernetes for Spark distributed testing ---"
	@kubectl apply -f k8s/spark-rbac.yaml
	@kubectl apply -f k8s/infrastructure/
	@echo "Waiting for infrastructure to be ready..."
	@sleep 30
	@kubectl get pods

k8s-benchmark: ## 📊 Run distributed benchmark on Kubernetes
	@echo "--- Running Kubernetes distributed benchmark ---"
	@chmod +x scripts/k8s_benchmark.sh
	@./scripts/k8s_benchmark.sh

k8s-clean: ## 🧽 Clean up Kubernetes resources
	@echo "--- Cleaning up Kubernetes resources ---"
	@kubectl delete -f k8s/infrastructure/ --ignore-not-found=true
	@kubectl delete -f k8s/spark-rbac.yaml --ignore-not-found=true
	@kubectl delete jobs --all --ignore-not-found=true

# Spark Operator commands (EKS)
spark-operator-install: ## 🎯 Install Spark Operator on EKS
	@echo "--- Installing Spark Operator ---"
	@./k8s/spark-operator/install.sh

spark-operator-configure: ## 🔧 Configure IRSA for Spark ServiceAccount
	@echo "--- Configuring IRSA for Spark ---"
	@./k8s/spark-operator/configure-irsa.sh

spark-operator-verify: ## ✅ Verify Spark Operator installation
	@echo "--- Verifying Spark Operator ---"
	@kubectl get pods -n spark-operator
	@kubectl get sparkapplications

spark-deploy: ## 🚀 Deploy Spark ETL benchmark (usage: make spark-deploy MODE=bulk SIZE=medium)
	@echo "--- Deploying Spark ETL Benchmark ---"
	@./k8s/spark-operator/deploy-benchmark.sh $(or $(MODE),bulk) $(or $(SIZE),medium) $(or $(REGION),eu-central-1)

spark-monitor: ## 👀 Monitor Spark applications (usage: make spark-monitor APP=<name>)
	@./k8s/spark-operator/monitor.sh $(APP)

spark-cleanup: ## 🧹 Clean up Spark applications (usage: make spark-cleanup MODE=all|completed|failed)
	@./k8s/spark-operator/cleanup.sh $(or $(MODE),all)

# Terraform commands
tf-init: ## 🏗️ Initialize Terraform working directory
	@echo "--- Initializing Terraform ---"
	@cd terraform && terraform init

tf-plan: ## 📋 Generate and show Terraform execution plan
	@echo "--- Planning Terraform changes ---"
	@cd terraform && terraform plan

tf-apply: ## 🚀 Apply Terraform configuration to create/update infrastructure
	@echo "--- Applying Terraform configuration ---"
	@cd terraform && terraform apply

tf-destroy: ## 💥 Destroy all Terraform-managed infrastructure
	@echo "--- Destroying Terraform infrastructure ---"
	@echo "⚠️  WARNING: This will destroy all AWS resources!"
	@cd terraform && terraform destroy

tf-output: ## 📤 Show Terraform outputs
	@echo "--- Terraform Outputs ---"
	@cd terraform && terraform output

tf-validate: ## ✅ Validate Terraform configuration files
	@echo "--- Validating Terraform configuration ---"
	@cd terraform && terraform validate

# EC2 Polars commands
ec2-deploy: ## 🖥️ Deploy EC2 instance for Polars via Terraform
	@echo "--- Deploying EC2 instance for Polars ---"
	@echo "Setting ec2_create_instance=true in terraform.tfvars..."
	@cd terraform && terraform apply -var="ec2_create_instance=true"

ec2-deploy-graviton: ## 🦾 Deploy Graviton EC2 instance for Polars (20% cost savings)
	@echo "--- Deploying Graviton EC2 instance ---"
	@cd terraform && terraform apply -var="ec2_create_instance=true" -var="ec2_instance_type=r7g.2xlarge" -var="ec2_architecture=arm64"

ec2-benchmark: ## 📊 Run benchmark on EC2 via SSH (usage: make ec2-benchmark SIZE=small)
	@echo "--- Running EC2 Polars benchmark ---"
	@echo "SSH to instance and run: python -m src.etl.polars_etl_nyc_taxi --size $(or $(SIZE),small)"
	@cd terraform && eval $$(terraform output -raw ec2_ssh_command) "cd /opt/etl-benchmark && python -m src.etl.polars_etl_nyc_taxi --size $(or $(SIZE),small)"

ec2-benchmark-all: ## 🏆 Run all EC2 benchmarks (tiny through large)
	@echo "--- Running all EC2 benchmarks ---"
	@$(MAKE) ec2-benchmark SIZE=tiny
	@$(MAKE) ec2-benchmark SIZE=small
	@$(MAKE) ec2-benchmark SIZE=medium
	@$(MAKE) ec2-benchmark SIZE=large

ec2-ssh: ## 🔐 SSH to EC2 instance (auto-detected)
	@echo "--- Connecting to EC2 instance ---"
	@cd terraform && eval $$(terraform output -raw ec2_ssh_command)

ec2-logs: ## 📋 View EC2 CloudWatch logs
	@echo "--- Viewing EC2 CloudWatch logs ---"
	@LOG_GROUP=$$(cd terraform && terraform output -raw ec2_cloudwatch_log_group 2>/dev/null || echo "/aws/ec2/etl-benchmark-polars-etl"); \
	INSTANCE_ID=$$(cd terraform && terraform output -raw ec2_instance_id 2>/dev/null); \
	aws logs tail "$$LOG_GROUP" --log-stream-names "$$INSTANCE_ID/etl" --follow

ec2-status: ## 📊 Show EC2 instance status
	@echo "--- EC2 Instance Status ---"
	@cd terraform && terraform output | grep ec2

ec2-destroy: ## 💥 Destroy EC2 instance (keeps other infrastructure)
	@echo "--- Destroying EC2 instance ---"
	@echo "⚠️  WARNING: This will destroy the EC2 instance!"
	@cd terraform && terraform apply -var="ec2_create_instance=false"

# Full Benchmark Orchestration
benchmark-full-run: ## 🏆 Run complete benchmark across all sizes (EC2 + EKS)
	@echo "--- Running full benchmark orchestration ---"
	@$(PYTHON) scripts/run_full_benchmark.py

benchmark-nyc-taxi: ## 🚕 Run NYC Taxi ETL benchmark (usage: make benchmark-nyc-taxi SIZE=small STACK=polars)
	@echo "--- Running NYC Taxi ETL benchmark ---"
	@$(PYTHON) scripts/run_full_benchmark.py --size $(or $(SIZE),small) --stack $(or $(STACK),both)

benchmark-verify: ## ✅ Verify benchmark results match between Polars and Spark
	@echo "--- Verifying benchmark results ---"
	@$(PYTHON) scripts/validate_results.py

benchmark-metrics: ## 📊 Collect CloudWatch metrics from benchmark runs
	@echo "--- Collecting CloudWatch metrics ---"
	@$(PYTHON) scripts/collect_cloudwatch_metrics.py

# Cost Analysis
cost-analysis: ## 💰 Run cost analysis on benchmark results
	@echo "--- Running cost analysis ---"
	@$(PYTHON) scripts/analyze_benchmark_costs.py

cost-analysis-region: ## 🌍 Show regional pricing comparison (usage: make cost-analysis-region REGION=eu-central-1)
	@echo "--- Showing regional pricing ---"
	@$(PYTHON) scripts/show_regional_pricing.py $(or $(REGION),eu-central-1)

cost-test: ## 🧪 Test cost calculation logic
	@echo "--- Testing cost analysis ---"
	@$(PYTHON) scripts/test_cost_analysis.py

# Report Generation
report-generate: ## 📄 Generate comprehensive benchmark report
	@echo "--- Generating benchmark report ---"
	@$(PYTHON) scripts/generate_benchmark_report.py

report-presentation: ## 📊 Generate PowerPoint presentation from results
	@echo "--- Generating presentation ---"
	@$(PYTHON) scripts/generate_presentation.py

report-all: report-generate report-presentation ## 📑 Generate all reports and presentations
	@echo "✅ All reports generated"

# Comprehensive Cleanup
clean-benchmark: ## 🧹 Clean benchmark results and artifacts
	@echo "--- Cleaning benchmark results ---"
	@rm -rf benchmark_results/*.json
	@rm -rf benchmark_results/*.log
	@rm -rf data/output/*
	@echo "✅ Benchmark results cleaned"

clean-reports: ## 🧹 Clean generated reports and presentations
	@echo "--- Cleaning reports ---"
	@rm -rf artifacts/*.pptx
	@rm -rf reports/*.md
	@echo "✅ Reports cleaned"

clean-s3: ## 🧹 Clean S3 benchmark results (requires AWS credentials)
	@echo "--- Cleaning S3 benchmark results ---"
	@BUCKET_NAME=$$(cd terraform && terraform output -raw s3_bucket_name 2>/dev/null || echo "etl-benchmark-results"); \
	echo "Cleaning bucket: $$BUCKET_NAME"; \
	aws s3 rm s3://$$BUCKET_NAME/polars/ --recursive || true; \
	aws s3 rm s3://$$BUCKET_NAME/spark/ --recursive || true; \
	echo "✅ S3 results cleaned"

clean-all: clean clean-benchmark clean-reports docker-clean ## 🧽 Clean everything (code, benchmarks, reports, Docker)
	@echo "✅ Complete cleanup finished"

# Quick Start Workflows
quickstart-ec2: ## 🚀 Quick start: Deploy EC2 and run small benchmark
	@echo "--- Quick Start: EC2 Polars Benchmark ---"
	@$(MAKE) ec2-deploy
	@sleep 60
	@$(MAKE) ec2-benchmark SIZE=small
	@$(MAKE) cost-analysis
	@echo "✅ Quick start complete! Check benchmark_results/ for results"

quickstart-eks: ## 🚀 Quick start: Deploy Spark on EKS and run small benchmark
	@echo "--- Quick Start: EKS Spark Benchmark ---"
	@$(MAKE) spark-operator-install
	@$(MAKE) spark-operator-configure
	@$(MAKE) spark-deploy SIZE=small
	@$(MAKE) cost-analysis
	@echo "✅ Quick start complete! Check benchmark_results/ for results"

quickstart-full: ## 🚀 Quick start: Run complete comparison (EC2 + EKS)
	@echo "--- Quick Start: Full Comparison ---"
	@echo "This will deploy both EC2 and EKS, run benchmarks, and generate reports"
	@$(MAKE) quickstart-ec2
	@$(MAKE) quickstart-eks
	@$(MAKE) benchmark-verify
	@$(MAKE) report-all
	@echo "✅ Full comparison complete! Check artifacts/ for reports"

# Workflow Helpers
workflow-status: ## 📊 Show status of all infrastructure components
	@echo "--- Infrastructure Status ---"
	@echo ""
	@echo "Terraform:"
	@cd terraform && terraform output 2>/dev/null || echo "  Not initialized"
	@echo ""
	@echo "EC2 Instances:"
	@aws ec2 describe-instances --filters "Name=tag:Project,Values=etl-benchmark" --query 'Reservations[*].Instances[*].[InstanceId,State.Name,InstanceType]' --output table 2>/dev/null || echo "  No instances found"
	@echo ""
	@echo "EKS Cluster:"
	@kubectl cluster-info 2>/dev/null || echo "  Not connected"
	@echo ""
	@echo "Spark Applications:"
	@kubectl get sparkapplications 2>/dev/null || echo "  No Spark applications found"

workflow-costs: ## 💰 Show estimated costs for current infrastructure
	@echo "--- Current Infrastructure Costs ---"
	@$(PYTHON) scripts/analyze_benchmark_costs.py --current-only
