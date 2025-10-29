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
        k8s-setup k8s-benchmark k8s-clean

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

# Docker commands
docker-build: ## 🐳 Build both Docker images
	@echo "--- Building both Docker images ---"
	@$(DOCKER_CMD) build -f Dockerfile.spark -t spark-etl .
	@$(DOCKER_CMD) build -f Dockerfile.pythonic -t pythonic-etl .

docker-build-spark: ## ⚡ Build Spark ETL image only
	@echo "--- Building Spark ETL image ---"
	@$(DOCKER_CMD) build -f Dockerfile.spark -t spark-etl .

docker-build-pythonic: ## 🐍 Build Pythonic ETL image only
	@echo "--- Building Pythonic ETL image ---"
	@$(DOCKER_CMD) build -f Dockerfile.pythonic -t pythonic-etl .

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
