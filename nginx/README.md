# SSL/HTTPS Setup with Nginx

This directory contains the Nginx configuration for production deployment with SSL/HTTPS support.

## Quick Start with Let's Encrypt (Free SSL)

### Prerequisites
- Domain name pointing to your server (e.g., `app.hitechwaste.com.my`)
- Server with ports 80 and 443 accessible from internet
- Docker and Docker Compose installed

### Step 1: Initial SSL Certificate Setup

```bash
# Create necessary directories
mkdir -p nginx/ssl certbot_webroot

# Generate self-signed certificates for testing (optional)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/CN=localhost"

# Or use Let's Encrypt for production (recommended)
docker run --rm -v certbot_certs:/etc/letsencrypt \
  -v certbot_webroot:/var/www/certbot \
  certbot/certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  -d your-domain.com \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email
```

### Step 2: Update Configuration

Edit `docker-compose.prod.yml` and replace:
- `your-domain.com` with your actual domain
- Update any other environment variables as needed

### Step 3: Start Production Stack

```bash
# Start with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Check Nginx status
docker logs hitech_nginx
```

### Step 4: Verify SSL

Visit `https://your-domain.com` and verify:
- SSL certificate is valid
- HTTP redirects to HTTPS
- All pages load correctly

## Certificate Renewal

Certbot container automatically renews certificates every 12 hours.

## Testing Locally with Self-Signed Certificates

For local testing without a domain:

```bash
# Generate self-signed certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx/ssl/privkey.pem \
  -out nginx/ssl/fullchain.pem \
  -subj "/CN=localhost"

# Start with production overrides
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Access at https://localhost (you'll see a browser warning - this is expected)
```

## Troubleshooting

### Certificate Not Found
```bash
# Check if certificates exist
docker run --rm -v certbot_certs:/etc/letsencrypt \
  ls -la /etc/letsencrypt/live/
```

### Nginx Not Starting
```bash
# Check Nginx configuration
docker run --rm -v $(pwd)/nginx/nginx.conf:/etc/nginx/nginx.conf:ro \
  nginx:alpine nginx -t

# Check logs
docker logs hitech_nginx
```

### Port Conflicts
Ensure ports 80 and 443 are not in use:
```bash
# Check what's using the ports
netstat -tulpn | grep -E ':(80|443)'
```

## Security Notes

- Never commit SSL certificates to version control
- Use strong SSL configuration (already included in nginx.conf)
- Enable HSTS (already included in nginx.conf)
- Keep Nginx updated for security patches
- Monitor certificate expiration dates
