# Hi-Tech Waste Management - User Manual

This manual guides users through the Hi-Tech Waste Management system.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Dashboard](#dashboard)
3. [Client Management](#client-management)
4. [Job Scheduling](#job-scheduling)
5. [Fleet Management](#fleet-management)
6. [Weighbridge Operations](#weighbridge-operations)
7. [Scheduled Waste Compliance](#scheduled-waste-compliance)
8. [Recyclables Management](#recyclables-management)
9. [Destruction Services](#destruction-services)
10. [Invoicing](#invoicing)
11. [ESG Reporting](#esg-reporting)
12. [AI Assistant](#ai-assistant)

## Getting Started

### First Login

1. Open your browser and navigate to: `https://your-domain.com`
2. Enter your email address and password
3. Click "Sign In"
4. **Important**: Change your password immediately after first login

### Password Change

1. Click your profile icon in the top-right corner
2. Select "Change Password"
3. Enter your current password
4. Enter your new password (minimum 8 characters)
5. Click "Update Password"

### Navigation

The main navigation is located on the left sidebar:
- **Dashboard**: Overview of operations
- **Clients**: Manage client information
- **Jobs**: Schedule and manage jobs
- **Fleet**: Vehicle and driver management
- **Weighbridge**: Weight recording operations
- **Compliance**: Scheduled waste compliance
- **Recyclables**: Recyclable materials tracking
- **Destruction**: Destruction job management
- **Invoicing**: Invoice generation and management
- **ESG**: Environmental reporting
- **AI Chat**: AI-powered assistance

## Dashboard

The dashboard provides an overview of your operations:

### Key Metrics
- **Active Jobs**: Number of jobs in progress
- **Pending Collections**: Jobs awaiting collection
- **Today's Collections**: Collections completed today
- **Revenue This Month**: Total invoiced amount

### Quick Actions
- **Create New Job**: Start a new collection job
- **Add Client**: Register a new client
- **Generate Report**: Create operational reports

### Recent Activity
- Latest job updates
- Recent compliance events
- System notifications

## Client Management

### Adding a New Client

1. Navigate to **Clients** from the sidebar
2. Click **"Add Client"** button
3. Fill in the required information:
   - **Company Name**: Legal business name
   - **Industry Vertical**: Type of industry (Manufacturing, Healthcare, etc.)
   - **SSM Number**: Business registration number
   - **Address**: Full business address
   - **Contact Person**: Primary contact name
   - **Phone**: Contact phone number
   - **Email**: Contact email address
4. Click **"Save Client"**

### Managing Waste Streams

1. Select a client from the client list
2. Click **"Waste Streams"** tab
3. Click **"Add Waste Stream"**
4. Enter waste stream details:
   - **Waste Code**: DOE waste code (e.g., SW305)
   - **Description**: Waste description
   - **Quantity Type**: Unit of measurement
5. Click **"Save"**

### Viewing Client Information

- Click on any client to view detailed information
- View associated jobs, invoices, and compliance records
- Edit client information as needed

## Job Scheduling

### Creating a New Job

1. Navigate to **Jobs** from the sidebar
2. Click **"New Job"** button
3. Fill in job details:
   - **Client**: Select from dropdown
   - **Waste Stream**: Select waste type
   - **Scheduled Date**: Collection date
   - **Priority**: Normal, High, or Urgent
   - **Special Instructions**: Any special requirements
4. Assign vehicle and driver:
   - **Vehicle**: Select available vehicle
   - **Driver**: Select available driver
5. Click **"Create Job"**

### Managing Jobs

**View Job List:**
- All jobs are displayed in a table
- Filter by status, date, client, or priority
- Sort by any column

**Job Status:**
- **Pending**: Scheduled but not started
- **In Progress**: Currently being executed
- **Completed**: Successfully finished
- **Cancelled**: Job was cancelled

**Edit Job:**
- Click on a job to view details
- Make necessary changes
- Click **"Update Job"**

**Cancel Job:**
- Click on a job
- Click **"Cancel Job"** button
- Confirm cancellation

## Fleet Management

### Adding a Vehicle

1. Navigate to **Fleet** from the sidebar
2. Click **"Vehicles"** tab
3. Click **"Add Vehicle"**
4. Enter vehicle details:
   - **License Plate**: Vehicle registration number
   - **Vehicle Type**: Truck, compactor, etc.
   - **Capacity**: Maximum load capacity
   - **Status**: Active, Maintenance, Retired
5. Click **"Save Vehicle"**

### Managing Drivers

1. Navigate to **Fleet** from the sidebar
2. Click **"Drivers"** tab
3. Click **"Add Driver"**
4. Enter driver details:
   - **Name**: Full name
   - **License Number**: Driver's license
   - **Phone**: Contact number
   - **Status**: Active, On Leave, Inactive
5. Click **"Save Driver"**

### Vehicle Maintenance

1. Select a vehicle from the list
2. Click **"Maintenance"** tab
3. Click **"Add Maintenance Record"**
4. Enter maintenance details:
   - **Date**: Service date
   - **Type**: Routine, Repair, Inspection
   - **Description**: Work performed
   - **Cost**: Service cost
5. Click **"Save"**

## Weighbridge Operations

### Recording a Weighing

1. Navigate to **Weighbridge** from the sidebar
2. Click **"New Weighing"**
3. Enter weighing details:
   - **Job Reference**: Select associated job
   - **Vehicle**: Select vehicle
   - **Tare Weight**: Empty vehicle weight
   - **Gross Weight**: Loaded vehicle weight
   - **Net Weight**: Automatically calculated (Gross - Tare)
4. Click **"Record Weighing"**

### Viewing Weighbridge Records

- All weighings are displayed in a table
- Filter by date, vehicle, or job
- Export records to PDF or Excel

### Calibration

Regular calibration is recommended:
- Monthly calibration checks
- Annual professional calibration
- Record all calibration activities

## Scheduled Waste Compliance

### Creating a Scheduled Waste Batch

1. Navigate to **Compliance** from the sidebar
2. Click **"Scheduled Waste"** tab
3. Click **"New Batch"**
4. Enter batch details:
   - **SW Code**: DOE waste code
   - **Generator**: Waste generator information
   - **Quantity**: Waste quantity
   - **Unit**: Unit of measurement
   - **Collection Date**: Planned collection date
5. Click **"Create Batch"**

### Generating Consignment Notes

1. Select a scheduled waste batch
2. Click **"Generate Consignment Note"**
3. Review the generated note
4. Click **"Download PDF"** or **"Print"**

### Compliance Status

- **Pending**: Awaiting collection
- **Collected**: Waste collected
- **Processed**: Waste processed
- **Compliant**: All requirements met

### DOE Reporting

1. Navigate to **Compliance** > **DOE Reports**
2. Select reporting period
3. Click **"Generate Report"**
4. Download or submit to DOE

## Recyclables Management

### Recording Recyclable Collection

1. Navigate to **Recyclables** from the sidebar
2. Click **"New Collection"**
3. Enter collection details:
   - **Client**: Select client
   - **Material Type**: Type of recyclable (plastic, paper, metal, etc.)
   - **Quantity**: Amount collected
   - **Unit**: Unit of measurement
   - **Quality Grade**: Material quality (A, B, C)
4. Click **"Record Collection"**

### Managing Buyers

1. Navigate to **Recyclables** > **Downstream Buyers**
2. Click **"Add Buyer"**
3. Enter buyer details:
   - **Company Name**: Buyer company
   - **Contact Person**: Contact name
   - **Phone**: Contact number
   - **Material Types**: Materials they purchase
4. Click **"Save Buyer"**

### Creating Sales

1. Navigate to **Recyclables** > **Sales**
2. Click **"New Sale"**
3. Enter sale details:
   - **Buyer**: Select downstream buyer
   - **Material**: Material type
   - **Quantity**: Amount sold
   - **Price per Unit**: Unit price
   - **Total**: Automatically calculated
4. Click **"Create Sale"**

### Recovery Statistics

View recovery statistics:
- Total materials collected
- Revenue from sales
- Material breakdown by type
- Top performing materials

## Destruction Services

### Creating a Destruction Job

1. Navigate to **Destruction** from the sidebar
2. Click **"New Destruction Job"**
3. Enter job details:
   - **Goods Description**: Description of items to destroy
   - **Quantity**: Number of items
   - **Weight**: Total weight
   - **Destruction Method**: Incineration, shredding, etc.
   - **Scheduled Date**: Destruction date
   - **Location**: Destruction facility
4. Click **"Create Job"**

### Witnessing Destruction

1. Select a destruction job
2. Click **"Start Destruction"**
3. Enter witness information:
   - **Witness Name**: Person witnessing
   - **Witness ID**: Identification number
   - **Witness Signature**: Digital signature
4. Click **"Record Witness"**

### Generating Certificates

1. Select a completed destruction job
2. Click **"Generate Certificate"**
3. Review certificate details
4. Click **"Download PDF"**

### Destruction Statistics

- Total destruction jobs
- Items destroyed
- Certificates issued
- Destruction methods breakdown

## Invoicing

### Creating an Invoice

1. Navigate to **Invoicing** from the sidebar
2. Click **"New Invoice"**
3. Enter invoice details:
   - **Client**: Select client
   - **Invoice Date**: Date of invoice
   - **Due Date**: Payment due date
4. Add line items:
   - **Service Type**: Collection, disposal, etc.
   - **Description**: Service description
   - **Quantity**: Quantity or units
   - **Unit Price**: Price per unit
   - **Total**: Line item total
5. Click **"Create Invoice"**

### Invoice Status

- **Draft**: Not yet sent
- **Sent**: Sent to client
- **Paid**: Payment received
- **Overdue**: Past due date
- **Cancelled**: Invoice cancelled

### Sending Invoices

1. Select a draft invoice
2. Click **"Send Invoice"**
3. Review invoice
4. Click **"Confirm Send"**
5. Invoice is emailed to client

### Recording Payment

1. Select a sent invoice
2. Click **"Record Payment"**
3. Enter payment details:
   - **Payment Date**: Date of payment
   - **Amount**: Payment amount
   - **Payment Method**: Bank transfer, check, cash
   - **Reference**: Payment reference number
4. Click **"Record Payment"**

### Invoice Reports

- **Aging Report**: Outstanding invoices by age
- **Revenue Report**: Revenue over time period
- **Client Summary**: Revenue by client

## ESG Reporting

### Carbon Records

1. Navigate to **ESG** from the sidebar
2. Click **"Carbon Records"** tab
3. Click **"Add Record"**
4. Enter carbon footprint data:
   - **Activity Type**: Collection, transportation, etc.
   - **Emission Source**: Vehicle type, fuel type
   - **CO2 Emissions**: Carbon dioxide emitted
   - **Date**: Activity date
5. Click **"Save Record"**

### ESG Reports

1. Navigate to **ESG** > **Reports**
2. Select report type:
   - **Carbon Footprint**: Total emissions
   - **Waste Diversion**: Waste diverted from landfill
   - **Recycling Rate**: Percentage recycled
   - **Energy Consumption**: Energy used
3. Select reporting period
4. Click **"Generate Report"**

### Sustainability Goals

Set and track sustainability goals:
- Waste reduction targets
- Recycling rate targets
- Carbon reduction goals
- Energy efficiency targets

## AI Assistant

### Using the AI Chat

1. Navigate to **AI Chat** from the sidebar
2. Type your question in the chat box
3. Press Enter or click Send
4. AI provides intelligent responses

### AI Capabilities

The AI assistant can help with:
- **Compliance Questions**: DOE regulations, waste codes
- **Operational Guidance**: Best practices, procedures
- **Data Analysis**: Trends, insights from your data
- **Document Search**: Find information in uploaded documents
- **Report Generation**: Create custom reports

### Uploading Documents

1. Click the attachment icon in the chat
2. Select document to upload
3. AI analyzes the document
4. Ask questions about the document content

### AI Agents

The system includes specialized AI agents:
- **Compliance Agent**: DOE regulations and deadlines
- **Operations Agent**: Job scheduling and optimization
- **Fleet Agent**: Vehicle and driver management
- **Finance Agent**: Invoicing and payment insights
- **ESG Agent**: Environmental reporting guidance

## Common Tasks

### Daily Operations

1. **Morning**
   - Check dashboard for pending jobs
   - Review overnight notifications
   - Assign vehicles and drivers for today's jobs

2. **Throughout Day**
   - Record weighbridge operations
   - Update job statuses
   - Handle customer inquiries

3. **End of Day**
   - Review completed jobs
   - Generate daily reports
   - Plan tomorrow's schedule

### Weekly Tasks

- Review compliance deadlines
- Generate weekly reports
- Check vehicle maintenance schedules
- Review outstanding invoices

### Monthly Tasks

- Generate monthly ESG reports
- Review financial reports
- Update sustainability goals
- Schedule preventive maintenance

## Troubleshooting

### Common Issues

**Cannot Login**
- Verify correct email and password
- Clear browser cache
- Contact administrator if account locked

**Jobs Not Appearing**
- Check date filters
- Verify job status
- Refresh the page

**Weighbridge Not Recording**
- Check vehicle is selected
- Verify tare weight entered
- Contact support if issue persists

**Invoice Not Sending**
- Verify client email is correct
- Check email server configuration
- Contact administrator

### Getting Help

- **AI Assistant**: Use the AI chat for quick questions
- **User Manual**: Refer to this manual
- **Administrator**: Contact your system administrator
- **Support**: Email support@hitechwaste.com.my

## Best Practices

### Data Entry
- Double-check all entered data
- Use consistent formatting
- Enter complete information
- Validate data before saving

### Security
- Never share your password
- Lock your computer when away
- Change password regularly
- Report suspicious activity

### Efficiency
- Use keyboard shortcuts
- Save frequently used filters
- Batch similar operations
- Use AI assistant for guidance

### Quality
- Follow standard procedures
- Document exceptions
- Review work before submission
- Seek clarification when unsure

## Keyboard Shortcuts

- **Ctrl + K**: Quick search
- **Ctrl + N**: New job
- **Ctrl + S**: Save
- **Ctrl + F**: Find
- **Esc**: Close modal/dialog

## Support and Training

### Training Resources
- Video tutorials (available on request)
- Online documentation
- AI assistant guidance
- Scheduled training sessions

### Contact Support
- **Email**: support@hitechwaste.com.my
- **Phone**: [PROVIDE NUMBER]
- **Hours**: Monday-Friday, 9 AM - 6 PM

### Feedback
We value your feedback! Please provide suggestions for improvement to:
- **Email**: feedback@hitechwaste.com.my
- **Through the AI Assistant**: Type "I have feedback"
