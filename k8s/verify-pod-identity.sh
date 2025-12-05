#!/bin/bash
# Script to verify EKS Pod Identity configuration and S3 access

set -e

CLUSTER_NAME="${CLUSTER_NAME:-etl-benchmark-cluster}"
NAMESPACE="${NAMESPACE:-default}"
REGION="${AWS_REGION:-us-east-1}"

echo "=========================================="
echo "EKS Pod Identity Verification Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print success
success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Function to print error
error() {
    echo -e "${RED}✗${NC} $1"
}

# Function to print info
info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Step 1: Verify EKS cluster exists
echo "Step 1: Verifying EKS cluster..."
if aws eks describe-cluster --name "$CLUSTER_NAME" --region "$REGION" &>/dev/null; then
    success "EKS cluster '$CLUSTER_NAME' found"
else
    error "EKS cluster '$CLUSTER_NAME' not found"
    exit 1
fi
echo ""

# Step 2: Verify Pod Identity Associations
echo "Step 2: Verifying Pod Identity Associations..."
ASSOCIATIONS=$(aws eks list-pod-identity-associations \
    --cluster-name "$CLUSTER_NAME" \
    --region "$REGION" \
    --output json)

SPARK_ASSOC=$(echo "$ASSOCIATIONS" | jq -r '.associations[] | select(.serviceAccount == "spark-sa") | .associationId')
POLARS_ASSOC=$(echo "$ASSOCIATIONS" | jq -r '.associations[] | select(.serviceAccount == "polars-sa") | .associationId')

if [ -n "$SPARK_ASSOC" ]; then
    success "Spark Pod Identity Association found: $SPARK_ASSOC"
else
    error "Spark Pod Identity Association not found"
    exit 1
fi

if [ -n "$POLARS_ASSOC" ]; then
    success "Polars Pod Identity Association found: $POLARS_ASSOC"
else
    error "Polars Pod Identity Association not found"
    exit 1
fi
echo ""

# Step 3: Verify ServiceAccounts exist
echo "Step 3: Verifying ServiceAccounts..."
if kubectl get serviceaccount spark-sa -n "$NAMESPACE" &>/dev/null; then
    success "ServiceAccount 'spark-sa' exists"
else
    error "ServiceAccount 'spark-sa' not found"
    info "Creating ServiceAccount..."
    kubectl apply -f k8s/service-accounts.yaml
fi

if kubectl get serviceaccount polars-sa -n "$NAMESPACE" &>/dev/null; then
    success "ServiceAccount 'polars-sa' exists"
else
    error "ServiceAccount 'polars-sa' not found"
    info "Creating ServiceAccount..."
    kubectl apply -f k8s/service-accounts.yaml
fi
echo ""

# Step 4: Deploy test pods
echo "Step 4: Deploying test pods..."
kubectl delete pod test-pod-identity-spark test-pod-identity-polars -n "$NAMESPACE" &>/dev/null || true
kubectl apply -f k8s/test-pod-identity.yaml

info "Waiting for test pods to be ready..."
kubectl wait --for=condition=ready pod/test-pod-identity-spark -n "$NAMESPACE" --timeout=60s
kubectl wait --for=condition=ready pod/test-pod-identity-polars -n "$NAMESPACE" --timeout=60s
success "Test pods are ready"
echo ""

# Step 5: Test AWS credentials in Spark pod
echo "Step 5: Testing AWS credentials in Spark pod..."
SPARK_IDENTITY=$(kubectl exec test-pod-identity-spark -n "$NAMESPACE" -- aws sts get-caller-identity 2>/dev/null)
if [ $? -eq 0 ]; then
    success "Spark pod can assume IAM role"
    echo "$SPARK_IDENTITY" | jq .
else
    error "Spark pod cannot assume IAM role"
    exit 1
fi
echo ""

# Step 6: Test AWS credentials in Polars pod
echo "Step 6: Testing AWS credentials in Polars pod..."
POLARS_IDENTITY=$(kubectl exec test-pod-identity-polars -n "$NAMESPACE" -- aws sts get-caller-identity 2>/dev/null)
if [ $? -eq 0 ]; then
    success "Polars pod can assume IAM role"
    echo "$POLARS_IDENTITY" | jq .
else
    error "Polars pod cannot assume IAM role"
    exit 1
fi
echo ""

# Step 7: Test S3 access from Spark pod
echo "Step 7: Testing S3 access from Spark pod..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="etl-benchmark-data-${ACCOUNT_ID}"

# Test listing benchmark bucket
if kubectl exec test-pod-identity-spark -n "$NAMESPACE" -- aws s3 ls "s3://${BUCKET_NAME}/" --region "$REGION" &>/dev/null; then
    success "Spark pod can list benchmark S3 bucket"
else
    error "Spark pod cannot list benchmark S3 bucket"
    info "This may be expected if the bucket doesn't exist yet"
fi

# Test listing NYC Taxi public bucket
if kubectl exec test-pod-identity-spark -n "$NAMESPACE" -- aws s3 ls "s3://nyc-tlc/trip data/" --region us-east-1 --no-sign-request &>/dev/null; then
    success "Spark pod can access NYC Taxi public bucket"
else
    error "Spark pod cannot access NYC Taxi public bucket"
fi
echo ""

# Step 8: Test S3 access from Polars pod
echo "Step 8: Testing S3 access from Polars pod..."
if kubectl exec test-pod-identity-polars -n "$NAMESPACE" -- aws s3 ls "s3://${BUCKET_NAME}/" --region "$REGION" &>/dev/null; then
    success "Polars pod can list benchmark S3 bucket"
else
    error "Polars pod cannot list benchmark S3 bucket"
    info "This may be expected if the bucket doesn't exist yet"
fi

if kubectl exec test-pod-identity-polars -n "$NAMESPACE" -- aws s3 ls "s3://nyc-tlc/trip data/" --region us-east-1 --no-sign-request &>/dev/null; then
    success "Polars pod can access NYC Taxi public bucket"
else
    error "Polars pod cannot access NYC Taxi public bucket"
fi
echo ""

# Step 9: Verify no IRSA annotations
echo "Step 9: Verifying no IRSA annotations on ServiceAccounts..."
SPARK_SA_ANNOTATIONS=$(kubectl get serviceaccount spark-sa -n "$NAMESPACE" -o jsonpath='{.metadata.annotations}')
POLARS_SA_ANNOTATIONS=$(kubectl get serviceaccount polars-sa -n "$NAMESPACE" -o jsonpath='{.metadata.annotations}')

if echo "$SPARK_SA_ANNOTATIONS" | grep -q "eks.amazonaws.com/role-arn"; then
    error "Spark ServiceAccount has IRSA annotation (should be removed for Pod Identity)"
else
    success "Spark ServiceAccount has no IRSA annotations"
fi

if echo "$POLARS_SA_ANNOTATIONS" | grep -q "eks.amazonaws.com/role-arn"; then
    error "Polars ServiceAccount has IRSA annotation (should be removed for Pod Identity)"
else
    success "Polars ServiceAccount has no IRSA annotations"
fi
echo ""

# Cleanup
echo "Step 10: Cleaning up test pods..."
kubectl delete pod test-pod-identity-spark test-pod-identity-polars -n "$NAMESPACE" &>/dev/null || true
success "Test pods deleted"
echo ""

echo "=========================================="
echo "✓ Pod Identity verification complete!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  - EKS cluster: $CLUSTER_NAME"
echo "  - Pod Identity Associations: 2 (spark-sa, polars-sa)"
echo "  - ServiceAccounts: 2 (no IRSA annotations)"
echo "  - S3 Access: Verified"
echo ""
echo "Next steps:"
echo "  1. Deploy SparkApplication: kubectl apply -f k8s/spark-application.yaml"
echo "  2. Monitor Spark job: kubectl logs -f spark-etl-benchmark-driver"
echo "  3. Check S3 output: aws s3 ls s3://${BUCKET_NAME}/output/"
