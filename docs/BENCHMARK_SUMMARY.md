# Benchmark Summary: Spark vs Polars Crossover Analysis

## Quick Overview

**Goal:** Find where Spark becomes faster than Polars while tracking costs.

**Approach:** Generate 8 datasets on EKS, run benchmarks, analyze results.

**Expected Crossover:** 50-100M records (simple), 25-50M (complex)

**Total Cost:** ~$40 (one-time)

**Total Time:** ~10 hours

## The 8 Datasets

| # | Name | Records | Size | Why? |
|---|------|---------|------|------|
| 1 | tiny | 1M | 100MB | Polars baseline |
| 2 | small | 10M | 1GB | Polars should win |
| 3 | medium | 50M | 5GB | **Crossover zone** |
| 4 | large | 100M | 10GB | **Crossover zone** |
| 5 | xlarge | 250M | 25GB | Spark should win |
| 6 | medium-complex | 50M | 5GB | Test complexity |
| 7 | large-complex | 100M | 10GB | Spark advantage |
| 8 | xlarge-complex | 250M | 25GB | Max Spark advantage |

## Why These Sizes?

**Hypothesis:** Polars wins on small data due to:
- No cluster startup (saves 30-60s)
- No network shuffle
- Efficient single-node processing

**Hypothesis:** Spark wins on large data due to:
- Horizontal scaling (more nodes = more power)
- Distributed memory (not limited to 256GB)
- Better handling of complex operations

**The crossover happens where Spark's advantages outweigh its overhead.**

## Instance Type Recommendation: Graviton

### Why Graviton (ARM) over x86?

| Benefit | Savings |
|---------|---------|
| **Cost** | 20% cheaper |
| **Performance** | 10-15% faster (some workloads) |
| **Memory bandwidth** | Better |
| **Energy efficiency** | 60% less power |

**Recommended configuration:**
```hcl
spark_workers_config = {
  instance_type = "r6g.2xlarge"  # 8 vCPU, 64GB, $0.40/hr
  min_size      = 0
  max_size      = 10
  desired_size  = 0  # Scale from zero!
}

polars_workers_config = {
  instance_type = "r6g.8xlarge"  # 32 vCPU, 256GB, $1.62/hr
  min_size      = 0
  max_size      = 2
  desired_size  = 0  # Scale from zero!
}
```

**Key:** Always scale to zero when not running benchmarks!

## Cost Breakdown

### One-Time Costs

| Item | Cost | Time |
|------|------|------|
| Infrastructure setup (Terraform) | $0 | 30 min |
| Generate 8 datasets | $15 | 4-6 hours |
| **Total Setup** | **$15** | **~6 hours** |

### Per Benchmark Cycle

| Item | Cost | Time |
|------|------|------|
| Run 8 datasets × Spark | $6 | 1.5 hours |
| Run 8 datasets × Polars | $13 | 1.5 hours |
| S3 operations | $1 | - |
| **Total per cycle** | **$20** | **~3 hours** |

### Monthly Costs (if running 24/7)

| Component | Cost/Month |
|-----------|------------|
| EKS Control Plane | $73 |
| NAT Gateways (3) | $100 |
| Spark workers (Graviton, 2 nodes) | $584 |
| Polars worker (Graviton, 1 node) | $1,170 |
| S3 storage (100GB) | $3 |
| **Total (if always on)** | **$1,930** |

**💡 Pro Tip:** Scale to zero when not benchmarking → Only pay $173/month baseline!

## Expected Results

### Performance Predictions

**Tiny (1M records):**
- Polars: 0.5s → **Winner by 70x**
- Spark: 35s (30s startup overhead)

**Small (10M records):**
- Polars: 2s → **Winner by 20x**
- Spark: 40s

**Medium (50M records):**
- Polars: 10s → **Winner by 5x**
- Spark: 50s

**Large (100M records):**
- Polars: 25s → **Close race! 🎯**
- Spark: 30s (without startup)

**XLarge (250M records):**
- Polars: 80s (may hit memory limits)
- Spark: 60s → **Winner by 1.3x**

### Crossover Point

**Simple operations:** Between 100M-250M records
**Complex operations:** Between 50M-100M records
**Memory pressure:** Earlier crossover if Polars hits RAM limits

## Key Insights We'll Discover

1. **At what size does Spark become faster?**
   - Expected: 100M+ records for simple ops
   - Expected: 50M+ records for complex ops

2. **How much does startup overhead matter?**
   - Expected: Spark loses 30-60s every run
   - Impact: Huge for small data, negligible for large

3. **When does Polars hit memory limits?**
   - Expected: Around 200-300GB dataset (with 256GB RAM)
   - Solution: Spark scales horizontally

4. **What's the cost per million records?**
   - Expected: Polars cheaper for small data
   - Expected: Spark cheaper at scale (amortized overhead)

5. **Does Graviton provide real savings?**
   - Expected: 15-20% cost reduction
   - Expected: Similar or better performance

## Execution Plan

### Phase 1: Setup (30 minutes, $0)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit: Set instance types to r6g (Graviton)
make tf-init
make tf-plan
make tf-apply
```

### Phase 2: Generate Data (4-6 hours, $15)

```bash
# Option A: Generate all 8 datasets
make eks-generate-all-datasets

# Option B: Quick test with 4 datasets
make eks-generate-quick-test
```

### Phase 3: Run Benchmarks (3-4 hours, $20)

```bash
# Run all benchmarks
make eks-benchmark-all

# This will:
# 1. Scale up Spark workers
# 2. Run Spark on all 8 datasets
# 3. Scale up Polars worker
# 4. Run Polars on all 8 datasets
# 5. Collect metrics
# 6. Scale everything to zero
```

### Phase 4: Analyze (1 hour, $0)

```bash
# Generate comprehensive report
make eks-analyze-results

# Output:
# - Performance comparison charts
# - Cost analysis
# - Crossover point identification
# - Recommendations
```

## Deliverables

1. **Raw Metrics JSON** - All benchmark data
2. **Performance Charts** - Visual comparison
3. **Cost Analysis** - Detailed breakdown
4. **Decision Matrix** - When to use what
5. **PowerPoint Deck** - Executive summary

## Risk Mitigation

### Potential Issues

**1. Polars runs out of memory**
- **Solution:** Use r6g.12xlarge (384GB RAM)
- **Cost impact:** +$0.80/hour

**2. Costs exceed budget**
- **Prevention:** Set AWS budget alert at $50
- **Solution:** Scale to zero immediately
- **Backup:** Use Spot instances (90% cheaper)

**3. Graviton compatibility issues**
- **Test:** Run tiny dataset first
- **Fallback:** Switch to r6i (x86) instances

**4. S3 throttling**
- **Prevention:** Spread data across prefixes
- **Solution:** Request rate increase from AWS

## Success Criteria

✅ All 8 datasets generated successfully
✅ Both frameworks complete all benchmarks
✅ Crossover point identified
✅ Cost per record calculated
✅ Total cost under $50
✅ Comprehensive report generated

## Quick Start Commands

```bash
# 1. Deploy infrastructure
make tf-apply

# 2. Generate datasets (choose one)
make eks-generate-all-datasets      # Full: 8 datasets, $15, 6 hours
make eks-generate-quick-test        # Quick: 4 datasets, $8, 3 hours

# 3. Run benchmarks
make eks-benchmark-all              # $20, 3-4 hours

# 4. Analyze results
make eks-analyze-results            # Free, 5 minutes

# 5. Clean up (IMPORTANT!)
make eks-scale-to-zero              # Stop paying for idle nodes
make tf-destroy                     # When completely done
```

## Cost Optimization Tips

1. ✅ **Use Graviton** - 20% cheaper than x86
2. ✅ **Scale to zero** - Only pay when running
3. ✅ **Use Spot instances** - 60-90% cheaper (for non-critical)
4. ✅ **Delete data after** - Save S3 costs
5. ✅ **Set budget alerts** - Avoid surprises

## Timeline

| Day | Activity | Cost |
|-----|----------|------|
| Day 1 AM | Deploy infrastructure | $0 |
| Day 1 PM | Generate datasets | $15 |
| Day 2 AM | Run benchmarks | $20 |
| Day 2 PM | Analyze results | $0 |
| **Total** | **2 days** | **$35-40** |

## Next Steps

After completing benchmarks:

1. Review performance charts
2. Identify crossover point
3. Calculate cost per record
4. Create decision framework
5. Write blog post / presentation
6. Share findings with team

## Questions?

- Full strategy: [benchmark-strategy.md](benchmark-strategy.md)
- Dataset details: [benchmark-datasets.md](benchmark-datasets.md)
- Infrastructure: [../terraform/README.md](../terraform/README.md)
