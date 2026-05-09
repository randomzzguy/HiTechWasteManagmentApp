# Redis Caching Guide

This guide explains how to use the Redis caching layer in Hi-Tech Waste Management.

## Overview

The application includes a Redis cache layer to improve performance by caching frequently accessed data. Redis is already configured in the Docker Compose setup.

## Configuration

Redis is configured via the `REDIS_URL` environment variable:

```bash
REDIS_URL=redis://localhost:6379
```

## Using the Cache

### Direct Cache Operations

```python
from cache import cache

# Get value from cache
value = await cache.get("key")

# Set value in cache (with 1 hour expiration)
await cache.set("key", {"data": "value"}, expire_seconds=3600)

# Delete specific key
await cache.delete("key")

# Delete keys matching a pattern
await cache.delete_pattern("user:*")

# Clear all cache
await cache.clear()
```

### Using the @cached Decorator

The `@cached` decorator provides automatic caching for function results:

```python
from cache import cached

@cached("user_profile", expire_seconds=300)
async def get_user_profile(user_id: str):
    # Expensive database query
    return await db.execute(select(User).where(User.id == user_id))

# First call - executes function and caches result
profile = await get_user_profile("user-123")

# Subsequent calls - returns cached result (no DB query)
profile = await get_user_profile("user-123")
```

### Custom Cache Key Builder

For more control over cache keys, use a custom key builder:

```python
def user_cache_key(user_id: str, fields: list[str]):
    return f"user:{user_id}:{','.join(fields)}"

@cached("user_data", expire_seconds=600, key_builder=user_cache_key)
async def get_user_data(user_id: str, fields: list[str]):
    return await fetch_user_data(user_id, fields)
```

## Cache Invalidation Strategies

### Time-Based Expiration

Set appropriate expiration times based on data volatility:

- **Static data** (config, lookups): 1 hour to 1 day
- **User data**: 5-15 minutes
- **Real-time data**: 1-5 minutes or no caching
- **Computed aggregates**: 10-30 minutes

### Manual Invalidation

When data changes, invalidate related cache entries:

```python
# After updating user data
await cache.delete(f"user:{user_id}")

# Invalidate all user-related caches
await cache.delete_pattern("user:*")

# Invalidate specific pattern
await cache.delete_pattern("client:{client_id}:*")
```

### Write-Through Caching

Update cache when data changes:

```python
async def update_user(user_id: str, data: dict):
    # Update database
    await db.execute(update(User).where(User.id == user_id).values(**data))
    
    # Update cache
    await cache.set(f"user:{user_id}", data, expire_seconds=3600)
```

## Best Practices

### DO Cache

- **Reference data**: Industry types, waste codes, status values
- **User sessions**: Login tokens, user preferences
- **Aggregated data**: Statistics, counts, summaries
- **Expensive queries**: Complex joins, calculations
- **API responses**: External API calls with rate limits

### DON'T Cache

- **Real-time data**: GPS coordinates, live sensor readings
- **Sensitive data**: Passwords, tokens (use session storage instead)
- **Large datasets**: Files, images (use object storage)
- **Frequently changing data**: Inventory counts, transaction logs
- **User-specific data without expiration**: User permissions (stale data risk)

### Cache Key Naming

Use consistent, descriptive key patterns:

```
user:{user_id}
user:{user_id}:profile
client:{client_id}:stats
batch:{batch_id}:details
sw:{sw_code}:info
```

### Monitoring Cache Performance

Monitor cache hit rate and performance:

```python
# Add logging to track cache hits/misses
import logging
logger = logging.getLogger(__name__)

@cached("data", expire_seconds=3600)
async def get_data(key: str):
    logger.info(f"Cache miss for key: {key}")
    result = await fetch_data(key)
    return result
```

## Troubleshooting

### Redis Connection Failed

```bash
# Check if Redis is running
docker ps | grep redis

# Check Redis logs
docker logs hitech_redis

# Test Redis connection
docker exec -it hitech_redis redis-cli ping
```

### Cache Not Working

1. Verify Redis is connected in application logs
2. Check if cache decorator is applied correctly
3. Ensure async/await is used consistently
4. Verify cache key format matches expectations

### Stale Cache Data

1. Reduce expiration time for volatile data
2. Implement cache invalidation on data changes
3. Use cache patterns for bulk invalidation
4. Consider write-through caching for critical data

## Performance Tips

### Batch Operations

```python
# Good: Cache individual items
for user_id in user_ids:
    user = await cache.get(f"user:{user_id}")

# Better: Use bulk queries then cache
users = await bulk_fetch_users(user_ids)
for user in users:
    await cache.set(f"user:{user.id}", user, expire_seconds=3600)
```

### Pipeline Redis Commands

For high-throughput scenarios, use Redis pipelines:

```python
async def cache_many(items: dict):
    pipe = cache._client.pipeline()
    for key, value in items.items():
        pipe.set(key, json.dumps(value), ex=3600)
    await pipe.execute()
```

### Cache Warming

Pre-populate cache on application startup:

```python
async def warm_cache():
    # Load frequently accessed data
    waste_codes = await get_waste_codes()
    for code in waste_codes:
        await cache.set(f"sw_code:{code}", code, expire_seconds=86400)
```

## Production Considerations

### Redis Persistence

Configure Redis persistence for durability:

```yaml
# docker-compose.yml
redis:
  image: redis:7-alpine
  command: redis-server --appendonly yes
  volumes:
    - redis_data:/data
```

### Redis Memory Limits

Set max memory and eviction policy:

```yaml
redis:
  command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
```

### Monitoring

Monitor Redis metrics:
- Memory usage
- Hit rate
- Connection count
- Command throughput

Use tools like:
- Redis CLI: `INFO stats`
- Prometheus + Grafana
- RedisInsight (GUI)
