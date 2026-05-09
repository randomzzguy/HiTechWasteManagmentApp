# Administrator Setup Guide

This guide is for system administrators setting up and managing the Hi-Tech Waste Management system.

## Initial Setup

### First-Time Configuration

#### Step 1: Access the Admin Panel

1. Log in with the admin account provided
2. Navigate to **Settings** from the sidebar
3. You'll see the administration dashboard

#### Step 2: Company Configuration

1. Go to **Settings** > **Company**
2. Fill in your company information:
   - **Company Name**: Your legal business name
   - **Logo**: Upload company logo (PNG or JPG, max 2MB)
   - **Address**: Business address
   - **Phone**: Contact phone number
   - **Email**: Contact email address
   - **Business Registration**: SSM number or equivalent
   - **Tax ID**: Tax registration number
3. Click **"Save Configuration"**

#### Step 3: System Settings

1. Go to **Settings** > **System**
2. Configure system settings:
   - **Timezone**: Select your timezone (e.g., Asia/Kuala_Lumpur)
   - **Date Format**: Preferred date format
   - **Currency**: Currency for financial data
   - **Language**: System language
   - **Default Page**: Landing page for users
3. Click **"Save Settings"**

#### Step 4: Email Configuration

1. Go to **Settings** > **Email**
2. Configure email server:
   - **SMTP Server**: e.g., smtp.gmail.com
   - **SMTP Port**: e.g., 587 for TLS, 465 for SSL
   - **SMTP Username**: Email username
   - **SMTP Password**: Email password or app-specific password
   - **From Email**: Default sender email
   - **From Name**: Default sender name
3. Click **"Test Email"** to verify configuration
4. Click **"Save Configuration"**

#### Step 5: SMS Configuration (Optional)

1. Go to **Settings** > **SMS**
2. Configure SMS gateway:
   - **Provider**: Select SMS provider
   - **API Key**: Provider API key
   - **Sender ID**: Approved sender ID
3. Click **"Test SMS"** to verify
4. Click **"Save Configuration"**

## User Management

### Creating User Accounts

#### Step 1: Navigate to Users

1. Go to **Settings** > **Users**
2. Click **"Add User"** button

#### Step 2: Fill User Information

**Required Fields:**
- **Email**: User's email address (will be username)
- **Full Name**: User's full name
- **Role**: User role (Admin, Manager, Staff, Driver, Viewer)
- **Department**: User's department
- **Phone**: Contact phone number

**Optional Fields:**
- **Employee ID**: Internal employee ID
- **Position**: Job title

#### Step 3: Set Permissions

Based on role, configure access:
- **Admin**: Full system access
- **Manager**: Can create/edit jobs, view reports
- **Staff**: Can update job statuses, record operations
- **Driver**: Can view assigned jobs, update status
- **Viewer**: Read-only access

#### Step 4: Send Invitation

1. Click **"Send Invitation"**
2. User receives email with setup link
3. User sets their own password

### User Roles Explained

| Role | Permissions | Typical Users |
|------|-------------|---------------|
| **Admin** | Full system access, user management, configuration | System administrators, IT managers |
| **Manager** | Create/edit jobs, view all reports, manage clients | Operations managers, supervisors |
| **Staff** | Update job statuses, record operations, view assigned jobs | Dispatchers, coordinators |
| **Driver** | View assigned jobs, update job status, record deliveries | Drivers, collectors |
| **Viewer** | Read-only access to assigned data | External auditors, management reports |

### Managing Users

**Edit User:**
1. Go to **Settings** > **Users**
2. Click on user name
3. Update information as needed
4. Click **"Save Changes"**

**Deactivate User:**
1. Go to **Settings** > **Users**
2. Click on user name
3. Change status to "Inactive"
4. Click **"Save Changes"**

**Reset Password:**
1. Go to **Settings** > **Users**
2. Click on user name
3. Click **"Reset Password"**
4. User receives email with reset link

## Module Configuration

### Fleet Management Setup

#### Configure Vehicle Types

1. Go to **Settings** > **Fleet**
2. Click **"Vehicle Types"** tab
3. Click **"Add Vehicle Type"**
4. Enter type details:
   - **Type Name**: e.g., Compactor Truck
   - **Default Capacity**: Default load capacity
   - **Capacity Unit**: kg, tons, etc.
5. Click **"Save"**

#### Configure Maintenance Schedules

1. Go to **Settings** > **Fleet** > **Maintenance**
2. Click **"Add Schedule"**
3. Enter schedule details:
   - **Vehicle Type**: Select vehicle type
   - **Maintenance Type**: Routine, Inspection, etc.
   - **Interval**: Days, kilometers, or hours
   - **Reminder Days**: Days before due
4. Click **"Save"**

### Compliance Setup

#### Configure Waste Codes

1. Go to **Settings** > **Compliance**
2. Click **"Waste Codes"** tab
3. Click **"Add Waste Code"**
4. Enter waste code details:
   - **Code**: DOE waste code (e.g., SW305)
   - **Description**: Waste description
   - **Category**: Scheduled waste, general waste, etc.
   - **Storage Requirements**: Special storage needs
   - **Transport Requirements**: Special transport needs
5. Click **"Save"**

#### Configure Compliance Deadlines

1. Go to **Settings** > **Compliance** > **Deadlines**
2. Click **"Add Deadline"**
3. Enter deadline details:
   - **Deadline Type**: Reporting, collection, etc.
   - **Default Days**: Days before deadline to alert
   - **Alert Method**: Email, SMS, or both
4. Click **"Save"**

### Financial Setup

#### Configure Tax Settings

1. Go to **Settings** > **Financial**
2. Click **"Tax"** tab
3. Configure tax settings:
   - **Tax Rate**: Default tax percentage
   - **Tax ID**: Your tax registration number
   - **Tax Inclusive**: Prices include tax or not
4. Click **"Save"**

#### Configure Payment Terms

1. Go to **Settings** > **Financial** > **Payment Terms**
2. Click **"Add Payment Term"**
3. Enter term details:
   - **Term Name**: e.g., Net 30, Net 60
   - **Days**: Days until payment due
   - **Default**: Set as default term
4. Click **"Save"**

#### Configure Service Pricing

1. Go to **Settings** > **Financial** > **Pricing**
2. Click **"Add Service Price"**
3. Enter pricing details:
   - **Service Type**: Collection, disposal, etc.
   - **Base Price**: Base price per unit
   - **Unit**: kg, ton, trip, etc.
   - **Minimum Charge**: Minimum charge per service
4. Click **"Save"**

## Security Configuration

### Password Policy

1. Go to **Settings** > **Security**
2. Configure password policy:
   - **Minimum Length**: Minimum password characters (8+ recommended)
   - **Require Uppercase**: Require uppercase letters
   - **Require Lowercase**: Require lowercase letters
   - **Require Numbers**: Require numeric characters
   - **Require Special Characters**: Require special characters
   - **Password Expiry**: Days before password must be changed (90 recommended)
3. Click **"Save Policy"**

### Session Management

1. Go to **Settings** > **Security** > **Sessions**
2. Configure session settings:
   - **Session Timeout**: Minutes of inactivity before logout (30 recommended)
   - **Max Concurrent Sessions**: Maximum simultaneous logins per user
   - **Remember Me Duration**: Days for "Remember Me" (7 recommended)
3. Click **"Save Settings"**

### IP Whitelisting (Optional)

For enhanced security, restrict admin access to specific IPs:

1. Go to **Settings** > **Security** > **IP Whitelist**
2. Click **"Add IP"**
3. Enter IP address or range:
   - **IP Address**: e.g., 192.168.1.100
   - **Description**: e.g., Office network
4. Click **"Save"**

### Two-Factor Authentication (Optional)

If available in your deployment:

1. Go to **Settings** > **Security** > **2FA**
2. Enable two-factor authentication
3. Configure authenticator app settings
4. Test with your account first

## Backup Configuration

### Automated Backups

Backups are configured via Docker Compose. Verify configuration:

```bash
# Check backup service
docker compose ps postgres-backup

# View backup logs
docker compose logs postgres-backup

# Check backup directory
docker exec hitech_postgres_backup ls -la /backups/
```

### Backup Schedule

Default: Daily at 2 AM

To change schedule, edit `docker-compose.yml`:

```yaml
postgres-backup:
  command: >
    sh -c "chmod +x /backup_postgres.sh &&
           apk add --no-cache postgresql-client &&
           while true; do
             /backup_postgres.sh
             sleep 86400  # Change this value (in seconds)
           done"
```

### Backup Retention

Default: 30 days

To change retention, edit `scripts/backup_postgres.sh`:

```bash
RETENTION_DAYS=30  # Change this value
```

### Manual Backup

```bash
# Run backup script
python scripts/backup_postgres.sh
```

### Restore from Backup

```bash
# Run restore script
python scripts/restore_postgres.sh /backups/hitech_waste_YYYYMMDD_HHMMSS.sql.gz
```

## Monitoring Setup

### Application Monitoring

Sentry is configured for error tracking. Verify:

1. Check `backend/.env` for Sentry DSN
2. Verify Sentry is connected in logs:
   ```bash
   docker compose logs backend | grep Sentry
   ```

### Uptime Monitoring

Run uptime monitor:

```bash
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

### Log Monitoring

View application logs:

```bash
# Backend logs
docker compose logs -f backend

# Frontend logs
docker compose logs -f frontend

# All logs
docker compose logs -f
```

## Performance Optimization

### Database Connection Pool

Adjust based on traffic in `backend/.env`:

```bash
DB_POOL_SIZE=20          # Increase for high traffic
DB_MAX_OVERFLOW=40       # Increase for high traffic
DB_POOL_TIMEOUT=30       # Seconds to wait for connection
```

### Cache Configuration

Redis is configured for caching. Monitor cache effectiveness:

```bash
# Check Redis stats
docker exec hitech_redis redis-cli INFO stats
```

### Rate Limiting

Adjust rate limits in `backend/.env`:

```bash
RATE_LIMIT_MAX_REQUESTS=200    # Increase for high traffic
RATE_LIMIT_WINDOW_SECONDS=60
```

## System Maintenance

### Regular Maintenance Tasks

**Daily:**
- Check application logs for errors
- Verify backup jobs completed
- Monitor system resources

**Weekly:**
- Review user activity
- Check for failed jobs
- Verify email/SMS delivery
- Review security logs

**Monthly:**
- Test backup restoration
- Review and rotate secrets
- Check SSL certificate expiration
- Review system performance
- Update documentation

**Quarterly:**
- Security audit
- Performance review
- Capacity planning
- User training review
- License review

### System Updates

**Update Application:**

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# Run migrations
docker compose exec backend alembic upgrade head
```

**Update Docker Images:**

```bash
# Pull latest images
docker compose pull

# Restart services
docker compose up -d
```

## Troubleshooting

### Common Issues

#### Application Not Starting

```bash
# Check service status
docker compose ps

# Check logs
docker compose logs backend

# Restart service
docker compose restart backend
```

#### Database Connection Issues

```bash
# Check database is running
docker compose ps postgres

# Check database logs
docker compose logs postgres

# Test connection
docker exec hitech_postgres pg_isready -U hitech
```

#### Email Not Sending

1. Verify SMTP configuration in Settings
2. Check email server is accessible
3. Test with different email provider
4. Check firewall allows SMTP ports

#### High Memory Usage

```bash
# Check resource usage
docker stats

# Restart services
docker compose restart

# Increase memory limits in docker-compose.yml
```

### Getting Help

- **Documentation**: Refer to this guide and other documentation
- **AI Assistant**: Use built-in AI chat for guidance
- **Support**: Email support@hitechwaste.com.my
- **Emergency**: Call provided emergency number

## Best Practices

### Security

1. **Change All Default Passwords**
   - Admin account (first login)
   - Database password
   - MinIO credentials
   - Any API keys

2. **Regular Security Audits**
   - Review user access monthly
   - Check for inactive accounts
   - Review security logs
   - Update software regularly

3. **Backup Regularly**
   - Automated daily backups
   - Test restore monthly
   - Store backups off-site
   - Encrypt backup files

### Performance

1. **Monitor System Resources**
   - CPU, memory, disk usage
   - Database performance
   - Application response times

2. **Optimize Database**
   - Run VACUUM regularly
   - Update statistics
   - Review slow queries
   - Add indexes as needed

3. **Cache Effectively**
   - Enable Redis caching
   - Cache frequently accessed data
   - Monitor cache hit rate
   - Invalidate cache on data changes

### Reliability

1. **High Availability**
   - Use load balancer for multiple instances
   - Configure database replication
   - Use CDN for static assets
   - Implement failover procedures

2. **Disaster Recovery**
   - Document recovery procedures
   - Test disaster recovery plan
   - Maintain off-site backups
   - Have emergency contact procedures

## Administrator Checklist

### Initial Setup
- [ ] Company configuration completed
- [ ] System settings configured
- [ ] Email/SMS configured and tested
- [ ] Admin password changed
- [ ] Additional users created
- [ ] Roles and permissions assigned
- [ ] Module configurations completed
- [ ] Security settings configured
- [ ] Backups verified
- [ ] Monitoring configured

### Ongoing
- [ ] Daily log review
- [ ] Weekly security check
- [ ] Monthly backup test
- [ ] Quarterly security audit
- [ ] Regular system updates
- [ ] User access review
- [ ] Performance monitoring
- [ ] Documentation updates

## Contact Information

**Technical Support:**
- Email: support@hitechwaste.com.my
- Phone: [PROVIDE NUMBER]

**Emergency:**
- Phone: [PROVIDE NUMBER]
- 24/7 availability

**Documentation:**
- USER_MANUAL.md - End-user guide
- DATA_IMPORT.md - Data import guide
- DEPLOYMENT.md - Deployment guide
- TROUBLESHOOTING.md - Common issues
