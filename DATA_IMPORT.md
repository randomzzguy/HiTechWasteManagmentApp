# Data Import Guide

This guide explains how to populate the Hi-Tech Waste Management system with your own data.

## Overview

There are three ways to populate the system with data:

1. **Manual Entry** - Use the web interface for small amounts of data
2. **CSV Import** - Import bulk data using CSV templates
3. **API Integration** - Automated data sync via API

## Manual Entry

### When to Use Manual Entry

- Initial system setup
- Small data sets (< 50 records)
- One-time data entry
- Testing and validation

### Manual Entry Process

1. Log in to the system
2. Navigate to the appropriate module (Clients, Fleet, etc.)
3. Click "Add" or "New" button
4. Fill in the required fields
5. Click "Save"

### Data Entry Order

Recommended order for manual data entry:

1. **Company Information** (Settings > Configuration)
2. **Users** (Settings > Users)
3. **Vehicles** (Fleet > Vehicles)
4. **Drivers** (Fleet > Drivers)
5. **Clients** (Clients)
6. **Waste Streams** (per client)
7. **Downstream Buyers** (Recyclables > Buyers)

## CSV Import

### When to Use CSV Import

- Migrating from existing systems
- Large data sets (> 50 records)
- Bulk data updates
- Initial data population

### CSV Templates

CSV templates are provided for each data type. Download the appropriate template from the system:

- `clients_template.csv` - Client information
- `vehicles_template.csv` - Vehicle fleet
- `drivers_template.csv` - Driver information
- `waste_streams_template.csv` - Waste stream definitions
- `buyers_template.csv` - Downstream buyers

### CSV Import Process

#### Step 1: Download Template

1. Navigate to the module (e.g., Clients)
2. Click "Import Data" button
3. Click "Download Template"
4. Save the CSV file

#### Step 2: Prepare Your Data

1. Open the template in Excel or similar
2. Fill in your data
3. Follow the template format exactly
4. Save as CSV (not Excel format)

#### Step 3: Validate Data

Check for common issues:
- Empty required fields
- Invalid dates
- Duplicate records
- Incorrect data formats
- Special characters in text fields

#### Step 4: Import Data

1. Navigate to the module
2. Click "Import Data" button
3. Select your CSV file
4. Click "Preview" to check data
5. Click "Import" to process
6. Review import results

#### Step 5: Verify Import

1. Check the data in the system
2. Verify record counts
3. Spot-check a few records
4. Fix any errors

### CSV Template Specifications

#### Clients Template

| Column | Required | Format | Example |
|--------|----------|--------|---------|
| company_name | Yes | Text | "ABC Manufacturing Sdn Bhd" |
| industry_vertical | Yes | Text | "Manufacturing" |
| ssm_number | No | Text | "123456-A" |
| address | No | Text | "123 Jalan Industri, 40000 Shah Alam" |
| contact_person | Yes | Text | "John Doe" |
| phone | Yes | Text | "+60123456789" |
| email | Yes | Email | "john@abc.com" |

#### Vehicles Template

| Column | Required | Format | Example |
|--------|----------|--------|---------|
| license_plate | Yes | Text | "ABC 1234" |
| vehicle_type | Yes | Text | "Compactor Truck" |
| capacity | Yes | Number | 5000 |
| capacity_unit | Yes | Text | "kg" |
| status | Yes | Text | "Active" |
| year | No | Number | 2023 |
| make | No | Text | "Hino" |
| model | No | Text | "FB300" |

#### Drivers Template

| Column | Required | Format | Example |
|--------|----------|--------|---------|
| name | Yes | Text | "Ahmad bin Ali" |
| license_number | Yes | Text | "12345/12/2023" |
| phone | Yes | Text | "+60198765432" |
| email | No | Email | "ahmad@company.com" |
| status | Yes | Text | "Active" |
| hire_date | No | Date | "2023-01-15" |

#### Waste Streams Template

| Column | Required | Format | Example |
|--------|----------|--------|---------|
| client_id | Yes | UUID | "123e4567-e89b-12d3-a456-426614174000" |
| sw_code | Yes | Text | "SW305" |
| description | Yes | Text | "Chemical waste" |
| quantity_type | Yes | Text | "kg" |
| doe_category | Yes | Text | "Scheduled Waste" |

#### Downstream Buyers Template

| Column | Required | Format | Example |
|--------|----------|--------|---------|
| company_name | Yes | Text | "Recycle Malaysia Sdn Bhd" |
| contact_person | Yes | Text | "Lee Wei" |
| phone | Yes | Text | "+60161234567" |
| email | Yes | Email | "lee@recycle.com.my" |
| address | No | Text | "456 Jalan Recycle, 50000 Kuala Lumpur" |
| material_types | Yes | Text | "plastic,paper,metal" |

### Common CSV Import Errors

| Error | Cause | Solution |
|-------|--------|----------|
| Missing required field | Empty cell in required column | Fill in all required fields |
| Invalid date format | Date not in YYYY-MM-DD format | Use correct date format |
| Invalid email | Email format incorrect | Use valid email format |
| Duplicate record | Same record already exists | Remove duplicate or update existing |
| Invalid number | Text in number field | Use numeric values only |
| Encoding issues | Special characters not supported | Use UTF-8 encoding |

## API Integration

### When to Use API Integration

- Real-time data sync from other systems
- Automated data updates
- Integration with ERP/CRM systems
- Large-scale data migration

### API Authentication

All API requests require authentication:

```bash
# Login to get token
curl -X POST https://your-domain.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin@hitechwaste.com.my", "password": "your-password"}'

# Response includes access_token
# Use token in subsequent requests
```

### API Endpoints for Data Import

#### Create Client

```bash
curl -X POST https://your-domain.com/api/v1/clients \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "ABC Manufacturing",
    "industry_vertical": "Manufacturing",
    "ssm_number": "123456-A",
    "address": "123 Jalan Industri",
    "contact_person": "John Doe",
    "phone": "+60123456789",
    "email": "john@abc.com"
  }'
```

#### Create Vehicle

```bash
curl -X POST https://your-domain.com/api/v1/fleet/vehicles \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "license_plate": "ABC 1234",
    "vehicle_type": "Compactor Truck",
    "capacity": 5000,
    "capacity_unit": "kg",
    "status": "Active"
  }'
```

#### Create Driver

```bash
curl -X POST https://your-domain.com/api/v1/fleet/drivers \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Ahmad bin Ali",
    "license_number": "12345/12/2023",
    "phone": "+60198765432",
    "status": "Active"
  }'
```

### Bulk Import via API

For bulk imports, use a script to process multiple records:

```python
import requests
import csv

API_BASE = "https://your-domain.com/api/v1"
TOKEN = "your-access-token"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# Import clients from CSV
with open('clients.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        response = requests.post(
            f"{API_BASE}/clients",
            headers=headers,
            json=row
        )
        print(f"Imported {row['company_name']}: {response.status_code}")
```

## Data Validation

### Pre-Import Validation

Before importing data, validate:

1. **Data Completeness**
   - All required fields filled
   - No missing critical information

2. **Data Quality**
   - Valid email addresses
   - Correct phone number formats
   - Proper date formats
   - No special characters in IDs

3. **Data Consistency**
   - Consistent formatting
   - Standardized units
   - Valid references (e.g., client exists)

4. **Data Uniqueness**
   - No duplicate records
   - Unique identifiers
   - No conflicting data

### Post-Import Verification

After importing data:

1. **Record Counts**
   - Verify expected number of records
   - Check for missing records

2. **Data Spot-Check**
   - Randomly sample records
   - Verify data accuracy
   - Check relationships

3. **Functional Testing**
   - Test operations with imported data
   - Verify reports work correctly
   - Check calculations

## Data Migration from Existing Systems

### Migration Steps

#### Phase 1: Assessment

1. **Data Inventory**
   - List all data sources
   - Identify data types and volumes
   - Map data fields to system schema

2. **Data Analysis**
   - Identify data quality issues
   - Note data transformations needed
   - Plan data cleansing

#### Phase 2: Preparation

1. **Data Extraction**
   - Export data from source system
   - Convert to import format
   - Clean and validate data

2. **Mapping**
   - Create field mapping document
   - Define transformation rules
   - Handle data type conversions

#### Phase 3: Import

1. **Test Import**
   - Import sample data
   - Verify results
   - Adjust mapping as needed

2. **Full Import**
   - Import all data
   - Monitor for errors
   - Handle exceptions

#### Phase 4: Verification

1. **Data Verification**
   - Compare source vs target
   - Verify record counts
   - Spot-check data accuracy

2. **Functional Testing**
   - Test all operations
   - Verify reports
   - Check integrations

### Common Migration Challenges

| Challenge | Solution |
|-----------|----------|
| Different data formats | Use transformation scripts |
| Missing data | Set default values or flag for review |
| Data inconsistencies | Clean data before import |
| Large data volumes | Import in batches |
| Complex relationships | Import in dependency order |

## Data Backup Before Import

Always backup before importing:

```bash
# Database backup
docker exec hitech_postgres pg_dump -U hitech hitech_waste > backup_before_import.sql

# Or use backup script
python scripts/backup_postgres.sh
```

## Data Security

### Sensitive Data Handling

- **Personal Data**: Encrypt if possible, limit access
- **Financial Data**: Secure storage, audit trail
- **Contact Information**: GDPR compliance

### Access Control

- Only authorized personnel can import
- Log all import activities
- Review import logs regularly

## Troubleshooting

### Import Fails

1. Check CSV format
2. Verify required fields
3. Check for special characters
4. Review error messages
5. Test with sample data

### Data Appears Incorrect

1. Verify template used correctly
2. Check data formats
3. Review transformation rules
4. Re-import with corrections

### Performance Issues

1. Import in smaller batches
2. Import during off-peak hours
3. Close other applications
4. Check system resources

## Best Practices

1. **Start Small**
   - Test with sample data first
   - Validate before full import
   - Gradually increase volume

2. **Backup Regularly**
   - Backup before any import
   - Keep multiple backup versions
   - Test restore procedures

3. **Document Everything**
   - Document data sources
   - Record transformation rules
   - Note any manual corrections

4. **Validate Thoroughly**
   - Pre-import validation
   - Post-import verification
   - Ongoing quality checks

5. **Plan for Errors**
   - Have rollback procedure
   - Prepare error handling
   - Document common issues

## Support

For data import assistance:
- **Email**: support@hitechwaste.com.my
- **Documentation**: See USER_MANUAL.md
- **AI Assistant**: Use built-in AI chat for guidance
