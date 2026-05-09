# Hi-Tech Waste Management - Deployment Guide

This guide covers deploying the Hi-Tech Waste Management application to production.

## Prerequisites

- Docker and Docker Compose installed
- PostgreSQL database (or use provided TimescaleDB container)
- Redis server (or use provided Redis container)
- Domain name configured with DNS
- SSL certificate (for HTTPS)

## Quick Start

### 1. Clone Repository

```bash
git clone <repository-url>
cd HiTechWasteManagmentApp
```

### 2. Configure Environment Variables

```bash
# Copy example environment file
cp backend/.env.example backend/.env

# Generate secure secrets
python backend/generate_secrets.py

# Edit .env with your values
nano backend/.env
```

### 3. Start Services

```bash
# Start all services
docker compose up -d

# Check service status
docker compose ps
```

### 4. Run Database Migrations

```bash
# From backend directory
cd backend

# Run migrations
alembic upgrade head
```

### 5. Verify Application

```bash
# Check backend health
curl http://localhost:8000/

# Check frontend
curl http://localhost:3000/
```

## Production Deployment

### 1. Prepare Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Add user to docker group
sudo usermod -aG docker $USER
```

### 2. Configure Environment

Create production `.env` file:

```bash
# Database
POSTGRES_PASSWORD=<secure-password>
DATABASE_URL=postgresql://hitech:<password>@localhost:5432/hitech_waste

# Secrets
JWT_SECRET=<secure-32+char-secret>
NEXTAUTH_SECRET=<secure-32+char-secret>
MINIO_ACCESS_KEY=<secure-access-key>
MINIO_SECRET_KEY=<secure-secret-key>

# CORS
ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com

# Monitoring (optional)
SENTRY_DSN=https://your-sentry-dsn
SENTRY_ENVIRONMENT=production

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60
```

### 3. Set Up SSL/HTTPS

Option 1: Use Nginx with Let's Encrypt (Recommended)

```bash
# Start with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Generate SSL certificate
docker run --rm -v certbot_certs:/etc/letsencrypt \
  -v certbot_webroot:/var/www/certbot \
  certbot/certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  -d your-domain.com \
  --email your-email@example.com \
  --agree-tos

# Restart nginx
docker compose restart nginx
```

Option 2: Use Existing SSL Certificates

```bash
# Create SSL directory
mkdir -p nginx/ssl

# Copy your certificates
cp your-cert.pem nginx/ssl/fullchain.pem
cp your-key.pem nginx/ssl/privkey.pem

# Update nginx configuration
```

### 4. Deploy Application

```bash
# Pull latest code
git pull origin main

# Build and start services
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Run migrations
docker compose exec backend alembic upgrade head
```

### 5. Enable Database Backups

```bash
# Start backup service
docker compose --profile backup up -d postgres-backup

# Verify backups
docker exec hitech_postgres_backup ls -la /backups/
```

### 6. Configure Monitoring

Enable Sentry error tracking (optional):

```bash
# Add Sentry DSN to .env
SENTRY_DSN=https://your-sentry-dsn
SENTRY_ENVIRONMENT=production

# Restart backend
docker compose restart backend
```

Set up uptime monitoring:

```bash
# Run uptime monitor
python scripts/uptime_monitor.py \
  --url https://your-domain.com \
  --interval 60 \
  --email-alerts \
  --smtp-host smtp.gmail.com \
  --smtp-port 587 \
  --smtp-user your-email@gmail.com \
  --smtp-password your-app-password \
  --alert-email admin@hitechwaste.com.my
```

## Deployment Checklist

### Pre-Deployment

- [ ] All secrets changed from defaults
- [ ] Environment variables configured
- [ ] SSL certificates obtained
- [ ] DNS records configured
- [ ] Database backup created
- [ ] Firewall rules configured
- [ ] Monitoring set up

### Deployment

- [ ] Code pulled from repository
- [ ] Docker images built
- [ ] Database migrations applied
- [ ] Services started successfully
- [ ] Health checks passing
- [ ] SSL/HTTPS working
- [ ] Application accessible

### Post-Deployment

- [ ] Verify all features working
- [ ] Check application logs
- [ ] Monitor error rates
- [ ] Test backup restoration
- [ ] Verify monitoring alerts
- [ ] Document any issues

## Scaling

### Horizontal Scaling

For multiple backend instances:

```yaml
# docker-compose.prod.yml
backend:
  deploy:
    replicas: 3
  resources:
    limits:
      cpus: '2'
      memory: 2G
```

### Database Scaling

For high database load:

1. Increase connection pool size in `.env`:
```bash
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
```

2. Use read replicas for read-heavy workloads

3. Consider TimescaleDB for time-series data

## Monitoring

### Application Logs

```bash
# View all logs
docker compose logs -f

# View specific service logs
docker compose logs -f backend
docker compose logs -f frontend
```

### Health Checks

```bash
# Backend health
curl http://localhost:8000/

# Database health
docker exec hitech_postgres pg_isready -U hitech

# Redis health
docker exec hitech_redis redis-cli ping
```

### Metrics

Use Prometheus + Grafana for metrics:

```yaml
# Add to docker-compose.yml
prometheus:
  image: prom/prometheus
  ports:
    - "9090:9090"
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml

grafana:
  image: grafana/grafana
  ports:
    - "3001:3000"
```

## Backup & Restore

### Database Backup

```bash
# Manual backup
docker exec hitech_postgres pg_dump -U hitech hitech_waste > backup.sql

# Using backup service
docker compose --profile backup up -d postgres-backup
```

### Database Restore

```bash
# Restore from backup
docker exec -i hitech_postgres psql -U hitech hitech_waste < backup.sql

# Using restore script
python scripts/restore_postgres.sh /backups/hitech_waste_YYYYMMDD_HHMMSS.sql.gz
```

## Troubleshooting

### Application Not Starting

```bash
# Check logs
docker compose logs backend

# Check service status
docker compose ps

# Restart service
docker compose restart backend
```

### Database Connection Issues

```bash
# Check database is running
docker compose ps postgres

# Check database logs
docker compose logs postgres

# Test connection
docker exec hitech_postgres pg_isready -U hitech
```

### SSL Certificate Issues

```bash
# Check certificate expiration
openssl x509 -in nginx/ssl/fullchain.pem -noout -dates

# Renew certificate
docker run --rm -v certbot_certs:/etc/letsencrypt \
  certbot/certbot renew
```

### High Memory Usage

```bash
# Check container resource usage
docker stats

# Increase memory limits in docker-compose.yml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 2G
```

## Security Best Practices

1. **Never commit .env files** to version control
2. **Use strong, unique passwords** for all services
3. **Enable HTTPS** in production
4. **Restrict database access** to local network only
5. **Keep dependencies updated** regularly
6. **Enable firewall** to restrict unnecessary ports
7. **Use secrets manager** for production credentials
8. **Enable audit logging** for sensitive operations
9. **Regular security audits** of the application
10. **Monitor for vulnerabilities** using tools like Dependabot

## Maintenance

### Regular Tasks

**Daily:**
- Check application logs for errors
- Verify backup jobs completed
- Monitor system resources

**Weekly:**
- Review security logs
- Check for dependency updates
- Verify SSL certificate expiration

**Monthly:**
- Test backup restoration
- Review and rotate secrets
- Performance optimization review
- Security audit

### Updates

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Run migrations
docker compose exec backend alembic upgrade head
```

## Support

For issues or questions:
- Check logs: `docker compose logs`
- Review documentation in respective directories
- Check GitHub issues
- Contact system administrator

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Next.js Documentation](https://nextjs.org/docs)
