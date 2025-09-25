# Makefile

# U# Phony targets are commands that don't represent a file.
# This tells 'make' to always execute the command regardless of whether a file with that name exists.
.PHONY: help install check format test all clean docker-build docker-up docker-down docker-logs docker-shell docker-test docker-build-spark docker-build-pythonic docker-run-spark docker-run-pythonic docker-benchmark docker-test-quick k8s-setup k8s-benchmark k8s-cleanbash for all commands
SHELL := /bin/bash

# Define the default goal, which will be executed when you just run "make"
.DEFAULT_GOAL := help

# Define the Python interpreter from our virtual environment
PYTHON := .venv/bin/python

# Define source code directories
SRC_DIR := src
TEST_DIR := tests

# Phony targets are commands that don't represent a file.
# This tells 'make' to always execute the command regardless of whether a file with that name exists.
.PHONY: help install check format test all clean docker-build docker-up docker-down docker-logs docker-shell docker-test docker-build-spark docker-build-pythonic docker-run-spark docker-run-pythonic docker-benchmark

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
check: ## Run code quality tools.
	@echo "🚀 Linting code: Running pre-commit"
	@git ls-files -- '*' | xargs uv run pre-commit run --files
	@echo "🚀 Installing missing types stubs"
	@uv pip install types-pytz
	@echo "🚀 Static type checking: Running mypy"
	@uv run mypy --install-types --non-interactive

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

# Docker commands
docker-build: ## 🐳 Build both Docker images
	@echo "--- Building both Docker images ---"
	@docker-compose build spark-etl pythonic-etl

docker-build-spark: ## ⚡ Build Spark ETL image only
	@echo "--- Building Spark ETL image ---"
	@docker build -f Dockerfile.spark -t spark-etl .

docker-build-pythonic: ## 🐍 Build Pythonic ETL image only
	@echo "--- Building Pythonic ETL image ---"
	@docker build -f Dockerfile.pythonic -t pythonic-etl .

docker-up: ## 🚀 Start infrastructure services
	@echo "--- Starting infrastructure services ---"
	@docker-compose up -d minio postgres
	@echo "Infrastructure started:"
	@echo "  - MinIO Console: http://localhost:9001"
	@echo "  - PostgreSQL: localhost:5432"

docker-run-spark: ## ⚡ Run Spark ETL (with infrastructure)
	@echo "--- Running Spark ETL ---"
	@docker-compose --profile spark up spark-etl

docker-run-pythonic: ## 🐍 Run Pythonic ETL (with infrastructure)
	@echo "--- Running Pythonic ETL ---"
	@docker-compose --profile pythonic up pythonic-etl

docker-test-quick: ## 🧪 Quick test of both ETL images without infrastructure
	@echo "--- Quick ETL image test ---"
	@mkdir -p data/input data/output
	@echo "Testing Pythonic ETL..."
	@docker run --rm -v $(shell pwd)/data:/app/data pythonic-etl || true
	@echo "Testing Spark ETL..."
	@docker run --rm -v $(shell pwd)/data:/app/data spark-etl || true
	@echo "Quick test completed."

docker-benchmark: ## 📊 Run performance benchmark comparison
	@echo "--- Running ETL performance benchmark ---"
	@python scripts/benchmark.py --data-size small

docker-down: ## 🛑 Stop all Docker services
	@echo "--- Stopping Docker services ---"
	@docker-compose down

docker-logs: ## 📋 Show logs from all Docker services
	@docker-compose logs -f

docker-shell: ## 🐚 Open a shell in the development container
	@docker-compose --profile dev up -d dev-env
	@docker-compose exec dev-env bash

docker-test: ## 🧪 Run tests inside Docker container
	@echo "--- Running tests in Docker container ---"
	@docker-compose --profile dev up -d dev-env
	@docker-compose exec dev-env python -m pytest tests/

docker-clean: ## 🧽 Remove Docker containers, networks, and volumes
	@echo "--- Cleaning up Docker resources ---"
	@docker-compose down -v --remove-orphans
	@docker system prune -f

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
