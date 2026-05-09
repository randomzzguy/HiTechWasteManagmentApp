# MinIO Production Configuration Guide

MinIO is used for object storage in the Hi-Tech Waste Management application.

## Current Setup

MinIO is configured in `docker-compose.yml` with:
- Default credentials (should be changed in production)
- Local volume storage
- Console on port 9002

## Production Configuration

### 1. Use Persistent Storage

MinIO data is already persisted via Docker volume `minio_data`. For production:

```yaml
# docker-compose.yml
minio:
  image: minio/minio:latest
  volumes:
    - minio_data:/data
  command: minio server /data --console-address ":9001"
```

### 2. Change Default Credentials

Update `.env` with secure credentials:

```bash
MINIO_ACCESS_KEY=your-secure-access-key-min-8-chars
MINIO_SECRET_KEY=your-secure-secret-key-min-8-chars
```

Generate secure credentials:

```bash
python backend/generate_secrets.py
```

### 3. Configure MinIO for Production

Update `docker-compose.yml` MinIO section:

```yaml
minio:
  image: minio/minio:latest
  container_name: hitech_minio
  restart: unless-stopped
  environment:
    MINIO_ROOT_USER: ${MINIO_ACCESS_KEY:-minioadmin}
    MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY:-minioadmin}
  ports:
    - "9000:9000"
    - "9002:9001"
  volumes:
    - minio_data:/data
  command: minio server /data --console-address ":9001" --address ":9000"
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
    interval: 30s
    timeout: 20s
    retries: 3
```

### 4. Create Buckets

Use the MinIO console or CLI to create required buckets:

```bash
# Install MinIO client
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
./mc alias set local http://localhost:9000 MINIO_ACCESS_KEY MINIO_SECRET_KEY

# Create buckets
./mc mb local/documents
./mc mb local/certificates
./mc mb local/reports
./mc mb local/uploads

# Set bucket policies
./mc anonymous set download local/documents
./mc anonymous set download local/certificates
```

### 5. Enable Versioning (Optional)

For data protection:

```bash
./mc version enable local/documents
```

### 6. Configure Lifecycle Policies

Automatically delete old files:

```bash
# Delete files older than 90 days in uploads bucket
./mc ilm add --expiry-days 90 local/uploads
```

## Backup MinIO Data

### Backup to Local Directory

```bash
# Mirror MinIO bucket to local directory
./mc mirror local/documents /backup/documents/
```

### Backup to Cloud Storage

Configure MinIO gateway mode or use rclone:

```bash
# Install rclone
rclone config

# Sync MinIO to S3
rclone sync local/documents s3:backup-bucket/
```

## MinIO Console

- **URL**: http://localhost:9002
- **Default credentials**: minioadmin/minioadmin (change in production)
- **Features**: Bucket management, file browser, user management

## Monitoring MinIO

### Health Check

```bash
curl http://localhost:9000/minio/health/live
```

### Metrics

MinIO exposes Prometheus metrics at `/minio/prometheus/metrics`.

Configure Prometheus scrape config:

```yaml
scrape_configs:
  - job_name: 'minio'
    static_configs:
      - targets: ['minio:9000']
    metrics_path: '/minio/prometheus/metrics'
```

## Security Best Practices

### 1. Use Strong Credentials

- Minimum 8 characters for access key
- Minimum 8 characters for secret key
- Use the provided `generate_secrets.py` script

### 2. Enable HTTPS

For production, enable HTTPS:

```yaml
minio:
  command: >
    minio server /data 
    --console-address ":9001" 
    --address ":9000"
    --certs /certs
```

Mount SSL certificates:

```yaml
volumes:
  - ./certs:/certs:ro
```

### 3. Network Isolation

- Don't expose MinIO ports publicly in production
- Use internal network for application access
- Only expose via reverse proxy with authentication

### 4. Access Control

- Create separate users for different applications
- Use bucket policies for fine-grained access
- Rotate credentials regularly

## Troubleshooting

### MinIO Not Starting

```bash
# Check logs
docker logs hitech_minio

# Check volume permissions
docker exec -it hitech_minio ls -la /data
```

### Access Denied Errors

1. Verify credentials in `.env`
2. Check bucket policies
3. Ensure correct endpoint URL in application config

### Data Not Persisting

1. Check volume is mounted correctly
2. Verify MinIO is writing to `/data`
3. Check disk space

## Scaling Considerations

### Distributed MinIO

For high availability, use distributed MinIO setup:

```yaml
minio1:
  image: minio/minio:latest
  command: minio server http://minio{1...4}/data --console-address ":9001"

minio2:
  image: minio/minio:latest
  command: minio server http://minio{1...4}/data --console-address ":9001"

minio3:
  image: minio/minio:latest
  command: minio server http://minio{1...4}/data --console-address ":9001"

minio4:
  image: minio/minio:latest
  command: minio server http://minio{1...4}/data --console-address ":9001"
```

### CDN Integration

For better performance, integrate with CDN:

1. Use CloudFront or similar
2. Configure MinIO as origin
3. Set up cache policies

## Application Integration

### Python (MinIO Client)

```python
from minio import Minio
from minio.error import S3Error

client = Minio(
    "localhost:9000",
    access_key=settings.MINIO_ACCESS_KEY,
    secret_key=settings.MINIO_SECRET_KEY,
    secure=False  # Use True in production with HTTPS
)

# Upload file
client.fput_object(
    "documents",
    "example.pdf",
    "/path/to/example.pdf"
)

# Download file
client.fget_object(
    "documents",
    "example.pdf",
    "/path/to/download.pdf"
)
```

### Environment Variables

The application uses these environment variables:

```bash
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=your-access-key
MINIO_SECRET_KEY=your-secret-key
```

## Additional Resources

- [MinIO Documentation](https://docs.min.io/)
- [MinIO Client Guide](https://min.io/docs/minio/linux/reference/minio-mc.html)
- [MinIO Best Practices](https://min.io/resources/minio-best-practices/)
