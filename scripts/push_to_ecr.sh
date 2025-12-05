#!/bin/bash
# Script to build and push Docker images to ECR
# Usage: ./scripts/push_to_ecr.sh [spark|polars|all] [version]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
IMAGE_TYPE="${1:-all}"
VERSION="${2:-latest}"
AWS_REGION="${AWS_REGION:-us-east-1}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ECR Image Build and Push Script${NC}"
echo -e "${GREEN}========================================${NC}"
echo "Image Type: $IMAGE_TYPE"
echo "Version: $VERSION"
echo "AWS Region: $AWS_REGION"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}Error: AWS CLI is not installed${NC}"
    exit 1
fi

# Check if Docker is available
if ! command -v docker &> /dev/null && ! command -v podman &> /dev/null; then
    echo -e "${RED}Error: Neither Docker nor Podman is installed${NC}"
    exit 1
fi

# Use podman if available, otherwise docker
DOCKER_CMD=$(command -v podman 2>/dev/null || command -v docker 2>/dev/null)
echo "Using container runtime: $DOCKER_CMD"
echo ""

# Get AWS account ID
echo "Getting AWS account ID..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
if [ -z "$AWS_ACCOUNT_ID" ]; then
    echo -e "${RED}Error: Failed to get AWS account ID. Check your AWS credentials.${NC}"
    exit 1
fi
echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo ""

# ECR registry URL
ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
echo "ECR Registry: $ECR_REGISTRY"
echo ""

# Authenticate with ECR
echo -e "${YELLOW}Authenticating with ECR...${NC}"
aws ecr get-login-password --region "$AWS_REGION" | \
    $DOCKER_CMD login --username AWS --password-stdin "$ECR_REGISTRY"

if [ $? -ne 0 ]; then
    echo -e "${RED}Error: Failed to authenticate with ECR${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Successfully authenticated with ECR${NC}"
echo ""

# Function to build and push an image
build_and_push() {
    local image_name=$1
    local dockerfile=$2
    local ecr_repo=$3

    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Building and pushing: $image_name${NC}"
    echo -e "${YELLOW}========================================${NC}"

    # Build the image
    echo "Building $image_name..."
    $DOCKER_CMD build -f "$dockerfile" -t "$image_name:$VERSION" .

    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to build $image_name${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ Successfully built $image_name:$VERSION${NC}"

    # Tag for ECR
    local ecr_image="${ECR_REGISTRY}/${ecr_repo}:${VERSION}"
    echo "Tagging as $ecr_image..."
    $DOCKER_CMD tag "$image_name:$VERSION" "$ecr_image"

    # Also tag as latest if version is not latest
    if [ "$VERSION" != "latest" ]; then
        local ecr_latest="${ECR_REGISTRY}/${ecr_repo}:latest"
        echo "Also tagging as $ecr_latest..."
        $DOCKER_CMD tag "$image_name:$VERSION" "$ecr_latest"
    fi

    # Push to ECR
    echo "Pushing to ECR..."
    $DOCKER_CMD push "$ecr_image"

    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to push $ecr_image${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ Successfully pushed $ecr_image${NC}"

    # Push latest tag if applicable
    if [ "$VERSION" != "latest" ]; then
        local ecr_latest="${ECR_REGISTRY}/${ecr_repo}:latest"
        echo "Pushing latest tag..."
        $DOCKER_CMD push "$ecr_latest"
        echo -e "${GREEN}✓ Successfully pushed $ecr_latest${NC}"
    fi

    echo ""
    return 0
}

# Build and push based on image type
case "$IMAGE_TYPE" in
    spark)
        build_and_push "spark-etl" "Dockerfile.spark" "spark-etl"
        ;;
    polars)
        build_and_push "polars-etl" "Dockerfile.pythonic" "polars-etl"
        ;;
    all)
        build_and_push "spark-etl" "Dockerfile.spark" "spark-etl"
        build_and_push "polars-etl" "Dockerfile.pythonic" "polars-etl"
        ;;
    *)
        echo -e "${RED}Error: Invalid image type '$IMAGE_TYPE'${NC}"
        echo "Usage: $0 [spark|polars|all] [version]"
        exit 1
        ;;
esac

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}All images successfully pushed to ECR!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "ECR Repository URLs:"
echo "  Spark:  ${ECR_REGISTRY}/spark-etl:${VERSION}"
echo "  Polars: ${ECR_REGISTRY}/polars-etl:${VERSION}"
echo ""
echo "To use these images in Kubernetes:"
echo "  kubectl set image deployment/spark-etl spark-etl=${ECR_REGISTRY}/spark-etl:${VERSION}"
echo "  kubectl set image deployment/polars-etl polars-etl=${ECR_REGISTRY}/polars-etl:${VERSION}"
echo ""
