# Strategic Pivot: "Vertical vs. Horizontal Scaling"

## Executive Summary

We've pivoted from a "Polars vs. Spark" comparison to a **"Vertical vs. Horizontal Scaling"** narrative. This reframing makes the benchmark more compelling, practical, and cost-focused.

## Why This Pivot?

### Original Approach Issues
- ❌ Required massive datasets (100M+ records) to show Spark winning
- ❌ Synthetic data generation was complex and time-consuming
- ❌ Narrative was "which is better?" (no clear answer)
- ❌ Missed the cost and operational complexity story

### New Approach Benefits
- ✅ Uses real-world NYC Taxi data (publicly available, no generation needed)
- ✅ Focuses on finding the **crossover point** where distributed processing becomes necessary
- ✅ Compares infrastructure approaches: EC2 (simple) vs. EKS (complex)
- ✅ Includes comprehensive cost analysis and TCO
- ✅ Answers a practical question: "When do I actually need Spark?"

## The New Narrative: "Ant vs. Cannon"

### The Ant (Vertical Scaling)
- **Technology**: Polars on single EC2 instance
- **Strengths**: Simple, fast for small-medium data, low cost, easy to debug
- **Weaknesses**: Limited by single machine resources, can't scale beyond RAM

### The Cannon (Horizontal Scaling)
- **Technology**: Spark on EKS cluster
- **Strengths**: Scales to massive datasets, fault-tolerant, handles data > RAM
- **Weaknesses**: Complex setup, higher cost, slower for small data, operational overhead

### The Question
**At what data size does the complexity of the cannon become worth it?**

## Key Changes

### Data Strategy
**Before**: Generate synthetic clickstream data
**After**: Use NYC Taxi public S3 bucket (`s3://nyc-tlc/trip data/`)

**Benefits**:
- No data generation compute needed
- No S3 upload costs
- Real production-grade data
- Multiple years available (2009-present)
- Already in Parquet format

### Infrastructure Strategy
**Before**: Both on EKS (Spark and Polars)
**After**: EC2 (Polars) vs. EKS (Spark)

**Benefits**:
- Clear infrastructure complexity comparison
- Shows operational overhead difference
- Demonstrates "right-sizing" principle
- More realistic deployment scenarios

### Authentication Strategy
**Before**: IRSA (IAM Roles for Service Accounts)
**After**: EKS Pod Identity Association

**Benefits**:
- Simpler configuration (no OIDC provider)
- No ServiceAccount annotations needed
- Better security isolation
- Easier to manage at scale

### Cost Focus
**Before**: Performance-only comparison
**After**: Performance + Cost + TCO

**Metrics**:
- Cost-per-GB-processed
- Cost-per-hour
- Operational overhead (deployment, monitoring, debugging)
- Total Cost of Ownership

## Implementation Impact

### Preserved Work
✅ All EKS/Terraform infrastructure (already built)
✅ Spark Operator installation (Task 11 completed)
✅ Docker builds and ECR integration
✅ Monitoring and metrics collection

### New Work Required
🆕 NYC Taxi ETL implementation (both Polars and Spark)
🆕 EC2 deployment automation
🆕 Pod Identity Association configuration
🆕 Cost analysis and TCO calculation
🆕 Crossover point identification

### Removed Work
❌ Synthetic data generation (Task 1, 14)
❌ Complex data generation on EKS
❌ Polars on EKS deployment

## Expected Results

### Crossover Point Hypothesis
Based on industry experience:

**Polars wins**: 1GB - 10GB (fits in single machine RAM)
- Faster startup
- Lower cost
- Simpler operations

**Spark wins**: 50GB+ (exceeds single machine capacity)
- Can process data > RAM
- Fault tolerance
- Scales horizontally

**Gray Zone**: 10GB - 50GB (depends on complexity and cost tolerance)

### Cost Analysis Example

**10GB Dataset Processing**:

**Polars (EC2 r6i.2xlarge)**:
- Instance: $0.504/hr × 0.1hr = $0.05
- S3 requests: ~$0.001
- **Total: $0.051**

**Spark (EKS 3 nodes)**:
- Control plane: $0.10/hr × 0.5hr = $0.05
- Nodes: 3 × $0.504/hr × 0.5hr = $0.756
- S3 requests: ~$0.002
- **Total: $0.808**

**Spark is 16x more expensive for 10GB!**

But at 100GB, Polars might OOM while Spark succeeds...

## Decision Framework

### Use Polars (EC2) When:
- Data size < 50GB
- Data fits in single machine RAM
- Simple ETL operations
- Cost is a concern
- Team is small/doesn't need K8s
- Fast iteration is important

### Use Spark (EKS) When:
- Data size > 100GB
- Data exceeds single machine capacity
- Complex joins/aggregations
- Need fault tolerance
- Already have K8s infrastructure
- Team has Spark expertise

### Consider Both When:
- Data size 50-100GB
- Workload complexity varies
- Cost vs. reliability tradeoff
- Evaluating technology stack

## Documentation Updates

### Updated Documents
✅ `requirements.md` - New requirements focused on crossover point and cost
✅ `design.md` - New architecture showing EC2 vs. EKS comparison
✅ `tasks.md` - New implementation plan with NYC Taxi ETL and EC2 deployment

### New Documents Needed
📝 `docs/DECISION_FRAMEWORK.md` - When to use each approach
📝 `docs/EC2_DEPLOYMENT.md` - EC2 setup guide
📝 `docs/COST_ANALYSIS.md` - Cost calculation methodology
📝 `docs/NYC_TAXI_ETL.md` - ETL logic documentation

## Next Steps

1. **Implement NYC Taxi ETL** (Phase 1)
   - Create data access module
   - Implement Polars version
   - Implement Spark version
   - Verify equivalence

2. **Deploy EC2 Infrastructure** (Phase 2)
   - Create Terraform module
   - Set up Polars environment
   - Test S3 access

3. **Update EKS for Pod Identity** (Phase 3)
   - Replace IRSA with Pod Identity
   - Update SparkApplication manifests
   - Test authentication

4. **Run Benchmarks** (Phase 4)
   - Execute across all data sizes
   - Collect metrics
   - Validate results

5. **Analyze and Report** (Phase 5)
   - Calculate costs
   - Identify crossover point
   - Generate reports

## Conclusion

This strategic pivot transforms the project from a simple "A vs. B" comparison into a practical guide for technology selection. By focusing on the crossover point and including comprehensive cost analysis, we provide actionable insights that help engineers make informed decisions.

The "Ant vs. Cannon" narrative is memorable and clearly communicates the core message: **use the right tool for the job, and don't over-engineer simple problems**.
