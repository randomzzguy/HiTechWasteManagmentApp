# Hi-Tech Waste Management — E2E Testing Suite

This directory contains comprehensive end-to-end tests for the Hi-Tech Waste Management application using Playwright.

## 📁 Test Structure

```
e2e/
├── playwright.config.ts          # Playwright configuration
├── package.json                  # Dependencies
├── tsconfig.json                 # TypeScript configuration
├── tests/
│   └── api/
│       ├── core-workflow.spec.ts  # Core business workflow tests
│       └── ai-features.spec.ts    # AI/RAG feature tests
└── README.md                     # This file
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd e2e
npm install
```

### 2. Install Playwright Browsers

```bash
npx playwright install
```

### 3. Set Environment Variables (Optional)

```bash
# Windows PowerShell
$env:TEST_API_URL="http://localhost:8000"
$env:TEST_USERNAME="admin@hitechwaste.com.my"
$env:TEST_PASSWORD="admin123"

# Or create .env file
echo "TEST_API_URL=http://localhost:8000" > .env
echo "TEST_USERNAME=admin@hitechwaste.com.my" >> .env
echo "TEST_PASSWORD=admin123" >> .env
```

### 4. Run Tests

```bash
# Run all API tests
npm test

# Run only core workflow tests
npx playwright test api/core-workflow.spec.ts

# Run only AI tests
npx playwright test api/ai-features.spec.ts

# Run with UI (headed mode)
npx playwright test --headed

# Run with trace viewer
npx playwright test --trace on

# Debug mode
npx playwright test --debug
```

## 🧪 Test Coverage

### Core Workflow Tests (`api/core-workflow.spec.ts`)

Tests the complete business workflow:

1. **Authentication**
   - Login with credentials
   - Token validation
   - Protected endpoint access

2. **Client Management**
   - Create new client
   - List and search clients
   - Client data validation

3. **Fleet Management**
   - List available vehicles
   - Create vehicle if needed
   - Driver management

4. **Job Lifecycle**
   - Create job for client
   - Assign vehicle and driver
   - Status transitions: draft → confirmed → dispatched → in_progress → completed
   - Job filtering and search

5. **Weighbridge Operations**
   - Create weight records
   - Calculate net weight (gross - tare)
   - Link to jobs
   - List with filters

6. **Finance & Invoicing**
   - Create invoice from job
   - Record payment
   - Verify invoice aging
   - Payment status tracking

7. **End-to-End Verification**
   - Full workflow: Job → Weighbridge → Invoice → Paid

### AI/RAG Tests (`api/ai-features.spec.ts`)

Tests AI-powered features:

1. **AI Chat**
   - Basic chat without RAG
   - RAG-enabled chat with client context
   - Conversation history
   - Temperature variations
   - Streaming responses

2. **Document Management**
   - Document upload for RAG
   - Document listing
   - Document deletion

3. **Agent Events**
   - List agent events
   - Event creation (if supported)
   - Mark events as read

4. **RAG Features**
   - Context retrieval
   - Document search
   - Client-scoped queries

5. **Database Agent**
   - Natural language queries
   - Schema information

6. **Error Handling**
   - Invalid requests
   - Authentication failures
   - Service unavailable scenarios

## ⚙️ Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_API_URL` | `http://localhost:8000` | Backend API base URL |
| `TEST_USERNAME` | `admin@hitechwaste.com.my` | Test user email |
| `TEST_PASSWORD` | `admin123` | Test user password |
| `CI` | - | Set to `true` for CI mode (retries, parallel limits) |

### Playwright Projects

- `chromium` - Desktop Chrome
- `firefox` - Desktop Firefox  
- `webkit` - Desktop Safari
- `Mobile Chrome` - Pixel 5 viewport
- `Mobile Safari` - iPhone 12 viewport
- `api` - API-only tests (no browser)

## 📊 Test Reports

After running tests, view the HTML report:

```bash
npm run report
```

Or check:
- `playwright-report/` - HTML test report
- `test-results.json` - JSON results
- `test-results/` - Traces, screenshots, videos

## 🔧 Backend Tests (pytest)

The backend also has pytest-based integration tests in `backend/tests/`:

```bash
cd backend
pytest tests/test_core_workflow_integration.py -v
pytest tests/test_ai_rag_integration.py -v
```

These tests use an in-memory SQLite database and test the full API layer.

## 🎯 Key Test Scenarios

### Scenario 1: Complete Job Workflow
```
Login → Create Client → Create Job 
→ Assign Vehicle/Driver → Dispatch Job
→ Record Weighbridge → Complete Job
→ Create Invoice → Record Payment
```

### Scenario 2: AI-Assisted Waste Query
```
Login → Upload Policy Document
→ Ask RAG Question → Verify Context-Aware Response
```

### Scenario 3: Fleet Management
```
Login → List Vehicles → Create Vehicle
→ Assign to Job → Update Status
```

## 🐛 Troubleshooting

### Tests fail with 401 Unauthorized
- Check credentials in environment variables
- Verify API is running and accessible
- Check if JWT secret matches

### AI tests skip with "LLM service unavailable"
- Ollama is not running: start with `ollama serve`
- Model not pulled: run `ollama pull llama3.1:8b`

### Database connection errors
- Ensure PostgreSQL is running
- Check DATABASE_URL in backend `.env`

### Port already in use
- Kill existing processes on port 8000 or 3000
- Or use different ports in environment variables

## 📝 Adding New Tests

1. Create `.spec.ts` file in `tests/api/` or `tests/ui/`
2. Use the existing patterns for authentication
3. Follow the naming convention: `feature-name.spec.ts`
4. Add to appropriate `test.describe()` block
5. Run with `npx playwright test path/to/test.spec.ts`

## 🔗 Related Files

- `backend/tests/test_core_workflow_integration.py` - Backend pytest tests
- `backend/tests/test_ai_rag_integration.py` - AI pytest tests
- `backend/pytest.ini` - pytest configuration
- `backend/main.py` - FastAPI application

## 📞 Support

For issues or questions:
1. Check test output and traces
2. Verify environment setup
3. Review API logs during test execution
