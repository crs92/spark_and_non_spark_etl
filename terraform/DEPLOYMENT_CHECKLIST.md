# Deployment Checklist

Use this checklist to ensure a smooth deployment of the ETL benchmark infrastructure.

## Pre-Deployment Checklist

### AWS Account Setup
- [ ] AWS account created and accessible
- [ ] AWS CLI installed (`aws --version`)
- [ ] AWS credentials configured (`aws configure`)
- [ ] Appropriate IAM permissions verified
  - [ ] EC2 (create instances, security groups)
  - [ ] EKS (create clusters, node groups)
  - [ ] S3 (create buckets, manage objects)
  - [ ] ECR (create repositories, push images)
  - [ ] IAM (create roles, policies)
  - [ ] VPC (create VPCs, subnets, gateways)

### Service Limits
- [ ] EKS cluster limit checked (default: 100)
- [ ] VPC limit checked (default: 5 per region)
- [ ] Elastic IP limit checked (default: 5 per region)
- [ ] EC2 instance limits checked:
  - [ ] r6i.2xlarge (need at least 10)
  - [ ] r6i.8xlarge (need at least 2)

### Local Tools
- [ ] Terraform >= 1.0 installed (`terraform version`)
- [ ] kubectl installed (`kubectl version --client`)
- [ ] jq installed (for JSON parsing)
- [ ] make installed (for Makefile targets)

### Cost Awareness
- [ ] Reviewed cost estimates (~$900-$3,800/month)
- [ ] AWS budget alerts configured
- [ ] Billing notifications enabled
- [ ] Cost allocation tags planned

## Deployment Checklist

### Step 1: Configuration
- [ ] Navigated to terraform directory (`cd terraform`)
- [ ] Copied example variables (`cp terraform.tfvars.example terraform.tfvars`)
- [ ] Edited terraform.tfvars with appropriate values:
  - [ ] aws_region set
  - [ ] environment set
  - [ ] cluster_name set
  - [ ] cluster_version set (>= 1.28)
  - [ ] spark_workers_config reviewed
  - [ ] polars_workers_config reviewed

### Step 2: Initialization
- [ ] Ran `make tf-init`
- [ ] Verified provider plugins downloaded
- [ ] Checked for initialization errors
- [ ] Reviewed .terraform.lock.hcl file

### Step 3: Validation
- [ ] Ran `make tf-validate`
- [ ] Configuration validated successfully
- [ ] No syntax errors reported

### Step 4: Planning
- [ ] Ran `make tf-plan`
- [ ] Reviewed resources to be created (~50-60 resources)
- [ ] Verified resource names and configurations
- [ ] Checked estimated costs
- [ ] No unexpected changes detected

### Step 5: Deployment
- [ ] Ran `make tf-apply`
- [ ] Reviewed plan one more time
- [ ] Typed `yes` to confirm
- [ ] Waited for deployment (~15-20 minutes)
- [ ] Deployment completed successfully
- [ ] No errors in output

### Step 6: Verification
- [ ] Ran `make tf-output`
- [ ] Saved important outputs:
  - [ ] cluster_name
  - [ ] cluster_endpoint
  - [ ] s3_bucket_name
  - [ ] ecr_repository_urls
  - [ ] spark_service_account_role_arn
  - [ ] polars_service_account_role_arn

### Step 7: Cluster Access
- [ ] Configured kubectl:
  ```bash
  aws eks update-kubeconfig --region <region> --name <cluster-name>
  ```
- [ ] Verified cluster access:
  ```bash
  kubectl get nodes
  ```
- [ ] Confirmed nodes are Ready
- [ ] Checked node labels:
  ```bash
  kubectl get nodes --show-labels
  ```

## Post-Deployment Checklist

### Kubernetes Setup
- [ ] Installed Spark Operator
- [ ] Created spark-sa service account
- [ ] Annotated spark-sa with IAM role ARN
- [ ] Created polars-sa service account
- [ ] Annotated polars-sa with IAM role ARN
- [ ] Verified service accounts:
  ```bash
  kubectl get serviceaccounts
  kubectl describe serviceaccount spark-sa
  kubectl describe serviceaccount polars-sa
  ```

### Container Images
- [ ] Logged into ECR:
  ```bash
  aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <registry-id>.dkr.ecr.<region>.amazonaws.com
  ```
- [ ] Built Spark image
- [ ] Tagged Spark image with ECR URL
- [ ] Pushed Spark image to ECR
- [ ] Built Polars image
- [ ] Tagged Polars image with ECR URL
- [ ] Pushed Polars image to ECR
- [ ] Verified images in ECR console

### S3 Setup
- [ ] Verified S3 bucket created
- [ ] Checked bucket versioning enabled
- [ ] Confirmed encryption enabled
- [ ] Tested bucket access from local machine:
  ```bash
  aws s3 ls s3://<bucket-name>/
  ```
- [ ] Created directory structure:
  ```bash
  aws s3api put-object --bucket <bucket-name> --key input/
  aws s3api put-object --bucket <bucket-name> --key output/
  ```

### Monitoring Setup
- [ ] Enabled Container Insights on EKS cluster
- [ ] Configured CloudWatch log groups
- [ ] Set up CloudWatch dashboards
- [ ] Created CloudWatch alarms:
  - [ ] High CPU usage
  - [ ] High memory usage
  - [ ] Node failures
  - [ ] Pod failures

### Security Review
- [ ] Reviewed security group rules
- [ ] Verified IAM role permissions
- [ ] Checked S3 bucket policies
- [ ] Confirmed encryption settings
- [ ] Reviewed CloudWatch logs access

### Cost Management
- [ ] Set up AWS Cost Explorer
- [ ] Created budget alerts
- [ ] Tagged all resources appropriately
- [ ] Documented expected monthly costs
- [ ] Planned scaling strategy

## Testing Checklist

### Basic Functionality
- [ ] Deployed test pod to cluster
- [ ] Verified pod can access S3
- [ ] Tested ECR image pull
- [ ] Checked pod logs in CloudWatch
- [ ] Verified IRSA working correctly

### ETL Workload Testing
- [ ] Uploaded test data to S3
- [ ] Submitted Spark test job
- [ ] Verified Spark job completion
- [ ] Checked output in S3
- [ ] Reviewed job logs
- [ ] Submitted Polars test job
- [ ] Verified Polars job completion
- [ ] Compared outputs

### Scaling Testing
- [ ] Scaled Spark node group up
- [ ] Verified new nodes joined cluster
- [ ] Scaled Spark node group down
- [ ] Verified nodes terminated gracefully
- [ ] Tested Polars node group scaling from 0

## Troubleshooting Checklist

### If Deployment Fails
- [ ] Checked Terraform error messages
- [ ] Reviewed AWS CloudTrail logs
- [ ] Verified AWS service limits
- [ ] Checked IAM permissions
- [ ] Reviewed VPC quota
- [ ] Ran `terraform plan` again
- [ ] Checked for resource conflicts

### If Cluster Access Fails
- [ ] Verified AWS credentials
- [ ] Checked kubectl configuration
- [ ] Reviewed IAM permissions
- [ ] Confirmed cluster endpoint accessible
- [ ] Checked security group rules
- [ ] Verified VPC configuration

### If Pods Can't Access S3
- [ ] Verified service account annotations
- [ ] Checked IAM role trust policy
- [ ] Reviewed S3 bucket policy
- [ ] Confirmed OIDC provider configured
- [ ] Tested IAM role assumption
- [ ] Checked pod environment variables

### If Images Won't Pull
- [ ] Verified ECR repository exists
- [ ] Checked image tags
- [ ] Confirmed node IAM role has ECR permissions
- [ ] Reviewed image pull secrets
- [ ] Checked ECR repository policies

## Cleanup Checklist

### Before Destroying Infrastructure
- [ ] Backed up important data from S3
- [ ] Exported CloudWatch logs
- [ ] Saved benchmark results
- [ ] Documented any custom configurations
- [ ] Notified team members

### Destruction Process
- [ ] Scaled all node groups to 0
- [ ] Deleted all Kubernetes resources
- [ ] Emptied S3 bucket (if desired)
- [ ] Ran `make tf-destroy`
- [ ] Typed `yes` to confirm
- [ ] Waited for destruction to complete
- [ ] Verified all resources deleted in AWS console

### Post-Destruction Verification
- [ ] Checked AWS console for orphaned resources
- [ ] Verified S3 bucket deleted (if intended)
- [ ] Confirmed ECR repositories deleted
- [ ] Checked for remaining EBS volumes
- [ ] Verified no lingering costs
- [ ] Reviewed final AWS bill

## Documentation Checklist

### Required Documentation
- [ ] Deployment date and time recorded
- [ ] AWS account ID documented
- [ ] Region documented
- [ ] Cluster name documented
- [ ] S3 bucket name documented
- [ ] ECR repository URLs documented
- [ ] IAM role ARNs documented
- [ ] Any custom configurations documented

### Team Communication
- [ ] Notified team of deployment
- [ ] Shared access instructions
- [ ] Documented any issues encountered
- [ ] Created runbook for common tasks
- [ ] Scheduled review meeting

## Success Criteria

Deployment is considered successful when:
- [ ] All Terraform resources created without errors
- [ ] EKS cluster accessible via kubectl
- [ ] Both node groups operational
- [ ] S3 bucket accessible
- [ ] ECR repositories created
- [ ] IAM roles configured correctly
- [ ] Test workload runs successfully
- [ ] Monitoring and logging operational
- [ ] Cost tracking configured
- [ ] Documentation complete

## Next Steps

After successful deployment:
1. [ ] Proceed to task 11.1: Install Spark Operator
2. [ ] Proceed to task 12: Build and deploy container images
3. [ ] Proceed to task 13: Update ETL code for S3 compatibility
4. [ ] Proceed to task 14: Generate large-scale datasets
5. [ ] Proceed to task 15: Run benchmarks on EKS

## Support Resources

- AWS Support: https://console.aws.amazon.com/support/
- EKS Documentation: https://docs.aws.amazon.com/eks/
- Terraform AWS Provider: https://registry.terraform.io/providers/hashicorp/aws/
- Project README: ../README.md
- Infrastructure Overview: INFRASTRUCTURE.md
- Quick Start Guide: QUICKSTART.md
