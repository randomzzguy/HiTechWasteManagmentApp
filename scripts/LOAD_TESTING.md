# Load Testing Guide

This guide covers load testing for the Hi-Tech Waste Management API endpoints using Locust.

## Prerequisites

Install Locust:

```bash
pip install locust
```

## Quick Start

### 1. Run Basic Load Test

```bash
# From project root
locust -f scripts/load_test.py --host http://localhost:8000
```

This opens the Locust web UI at http://localhost:8089.

### 2. Run Headless Load Test

```bash
locust -f scripts/load_test.py \
  --users 100 \
  --spawn-rate 10 \
  --headless \
  --run-time 5m \
  --host http://localhost:8000
```

## Load Test Scenarios

### Smoke Test

Quick sanity check with low load:

```bash
locust -f scripts/load_test.py \
  --users 10 \
  --spawn-rate 2 \
  --headless \
  --run-time 30s \
  --host http://localhost:8000
```

**Expected Results:**
- 0% failure rate
- Response time < 200ms
- No errors in logs

### Normal Load Test

Simulate typical daily traffic:

```bash
locust -f scripts/load_test.py \
  --users 100 \
  --spawn-rate 10 \
  --headless \
  --run-time 10m \
  --host http://localhost:8000
```

**Expected Results:**
- Failure rate < 1%
- Response time < 500ms
- CPU usage < 70%
- Memory usage stable

### Peak Load Test

Simulate peak traffic periods:

```bash
locust -f scripts/load_test.py \
  --users 500 \
  --spawn-rate 50 \
  --headless \
  --run-time 15m \
  --host http://localhost:8000
```

**Expected Results:**
- Failure rate < 5%
- Response time < 2s
- System remains stable
- No database connection pool exhaustion

### Stress Test

Push system to limits:

```bash
locust -f scripts/load_test.py \
  --users 1000 \
  --spawn-rate 100 \
  --headless \
  --run-time 20m \
  --host http://localhost:8000
```

**Expected Results:**
- Identify breaking point
- Document failure modes
- Measure degradation patterns
- Test auto-scaling (if applicable)

## Distributed Load Testing

For high-load tests requiring multiple machines:

### Master Node

```bash
locust -f scripts/load_test.py \
  --master \
  --expect-workers 4 \
  --host http://localhost:8000 \
  --users 2000 \
  --spawn-rate 200
```

### Worker Nodes

```bash
locust -f scripts/load_test.py \
  --worker \
  --master-host <master-ip>
```

## Custom Load Tests

### Create Custom Test Scenarios

Edit `scripts/load_test.py` to add custom scenarios:

```python
class CustomUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(5)
    def custom_endpoint(self):
        self.client.get("/api/v1/custom/endpoint")
    
    @task(1)
    def heavy_operation(self):
        self.client.post("/api/v1/custom/heavy", json={"data": "test"})
```

### Test Specific Endpoints

```python
class EndpointSpecificUser(HttpUser):
    @task
    def test_single_endpoint(self):
        self.client.get("/api/v1/compliance/sw-batches?skip=0&limit=50")
```

## Metrics to Monitor

### Key Performance Indicators

- **Requests per second (RPS)**: Throughput measure
- **Response time**: p50, p95, p99 percentiles
- **Failure rate**: Percentage of failed requests
- **Response time distribution**: Histogram of response times

### System Metrics

- **CPU usage**: Overall and per-container
- **Memory usage**: RAM consumption
- **Database connections**: Active vs available
- **Redis connections**: Cache performance
- **Disk I/O**: Storage performance
- **Network I/O**: Bandwidth usage

### Application Metrics

- **Error logs**: Application errors
- **Slow queries**: Database performance
- **Cache hit rate**: Redis effectiveness
- **Rate limit violations**: Throttling events

## Interpreting Results

### Success Criteria

| Metric | Target | Good | Warning | Critical |
|--------|--------|------|---------|----------|
| Failure Rate | < 1% | < 0.5% | 0.5-2% | > 2% |
| Response Time (p50) | < 200ms | < 100ms | 100-300ms | > 300ms |
| Response Time (p95) | < 500ms | < 300ms | 300-800ms | > 800ms |
| Response Time (p99) | < 1s | < 500ms | 500ms-2s | > 2s |
| RPS | Varies | Stable | Fluctuating | Dropping |

### Common Issues

#### High Failure Rate

**Causes:**
- Rate limiting triggered
- Database connection pool exhausted
- Memory limits reached
- Application errors

**Solutions:**
- Increase rate limit thresholds
- Increase connection pool size
- Add more resources
- Check application logs

#### High Response Times

**Causes:**
- Database queries slow
- Missing indexes
- Network latency
- CPU throttling

**Solutions:**
- Add database indexes
- Optimize queries
- Enable caching
- Scale resources

#### Memory Leaks

**Causes:**
- Unclosed connections
- Large object retention
- Memory fragmentation

**Solutions:**
- Profile memory usage
- Fix connection leaks
- Implement object pooling
- Restart services periodically

## Load Testing Checklist

### Before Load Test

- [ ] Application running in test environment
- [ ] Database restored from production backup (realistic data)
- [ ] Monitoring enabled (Sentry, logs)
- [ ] System metrics collection active
- [ ] Network stable
- [ ] Sufficient disk space for logs

### During Load Test

- [ ] Monitor application logs
- [ ] Watch system metrics
- [ ] Check database performance
- [ ] Verify rate limiting behavior
- [ ] Document any anomalies
- [ ] Capture screenshots of metrics

### After Load Test

- [ ] Review failure logs
- [ ] Analyze slow queries
- [ ] Check for memory leaks
- [ ] Document findings
- [ ] Identify bottlenecks
- [ ] Create improvement plan

## Performance Optimization

### Database Optimization

```sql
-- Check slow queries
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Check index usage
SELECT schemaname, tablename, indexname, idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan;
```

### Connection Pool Tuning

```bash
# In .env
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
```

### Caching Strategy

```python
# Add caching to frequently accessed endpoints
@cached("sw_batches", expire_seconds=300)
async def get_sw_batches():
    # Implementation
```

### Rate Limiting Adjustment

```bash
# In .env
RATE_LIMIT_MAX_REQUESTS=200
RATE_LIMIT_WINDOW_SECONDS=60
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Load Tests

on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM
  workflow_dispatch:

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install locust
      - run: docker compose up -d
      - run: sleep 30  # Wait for services to start
      - run: |
          locust -f scripts/load_test.py \
            --users 100 \
            --spawn-rate 10 \
            --headless \
            --run-time 5m \
            --host http://localhost:8000 \
            --html load_test_report.html
      - uses: actions/upload-artifact@v3
        with:
          name: load-test-report
          path: load_test_report.html
```

## Best Practices

1. **Test in realistic environment** - Use production-like data and configuration
2. **Gradually increase load** - Don't start with maximum load
3. **Monitor continuously** - Watch metrics throughout the test
4. **Document everything** - Record test parameters and results
5. **Test regularly** - Include load tests in CI/CD pipeline
6. **Compare results** - Track performance over time
7. **Test after changes** - Run load tests after major updates
8. **Plan for growth** - Test beyond current requirements

## Troubleshooting

### Locust Won't Start

```bash
# Check Python version
python --version  # Should be 3.8+

# Reinstall Locust
pip uninstall locust
pip install locust
```

### Connection Refused

```bash
# Verify application is running
curl http://localhost:8000/

# Check Docker containers
docker compose ps

# Check application logs
docker compose logs backend
```

### High Memory Usage

```bash
# Check Locust memory
top | grep locust

# Reduce number of users
--users 50  # Instead of 100
```

## Additional Resources

- [Locust Documentation](https://docs.locust.io/)
- [Load Testing Best Practices](https://www.blazemeter.com/blog/load-testing-best-practices)
- [Performance Testing Guide](https://www.guru99.com/performance-testing.html)
