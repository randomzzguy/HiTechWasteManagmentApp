# Testing Guide

This guide covers testing strategies and improving test coverage for the Hi-Tech Waste Management application.

## Current Test Coverage

### Backend Tests

Located in `backend/`:
- `test_api.py` - Basic API connectivity tests
- `test_auth_api.py` - Authentication endpoint tests
- `tests/test_ai_rag_integration.py` - AI/RAG integration tests
- `tests/test_core_workflow_integration.py` - Core workflow tests
- `tests/test_settings_users.py` - Settings and user tests

### Frontend Tests

Located in `frontend/src/`:
- `components/ai/sseUtils.test.ts` - SSE utility tests

## Running Tests

### Backend Tests

```bash
# From backend directory
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_ai_rag_integration.py

# Run with verbose output
pytest -v

# Run specific test
pytest tests/test_settings_users.py::test_user_creation
```

### Frontend Tests

```bash
# From frontend directory
cd frontend

# Run all tests
npm test

# Run with coverage
npm test -- --coverage

# Run in watch mode
npm test -- --watch

# Run specific test file
npm test sseUtils.test.ts
```

### E2E Tests

```bash
# From e2e directory
cd e2e

# Run E2E tests
npm test

# Run with Playwright UI
npx playwright test --ui
```

## Measuring Coverage

### Backend Coverage

```bash
# Install coverage tools
pip install pytest-cov

# Run tests with coverage
pytest --cov=. --cov-report=html --cov-report=term-missing

# View HTML report
open htmlcov/index.html
```

### Frontend Coverage

```bash
# Coverage is built into vitest
npm test -- --coverage

# View coverage report
open coverage/index.html
```

## Increasing Test Coverage to 80%+

### Priority Areas for Testing

#### High Priority (Critical Path)

1. **Authentication & Authorization**
   - Login/logout flows
   - Token refresh
   - Permission checks
   - Role-based access control

2. **Core Business Logic**
   - Scheduled waste batch creation
   - Job scheduling
   - Invoice generation
   - Compliance validation

3. **API Endpoints**
   - All CRUD operations
   - Error handling
   - Input validation
   - Edge cases

#### Medium Priority

1. **Database Operations**
   - CRUD operations on all models
   - Query optimization
   - Transaction handling
   - Migration safety

2. **External Integrations**
   - MinIO file operations
   - Ollama AI calls
   - Milvus vector operations
   - Email notifications

3. **Frontend Components**
   - Form validation
   - Data fetching
   - Error states
   - User interactions

#### Low Priority

1. **Utility Functions**
   - Helper functions
   - Data transformations
   - Formatting utilities

2. **UI Polish**
   - Visual components
   - Animations
   - Styling

### Testing Strategy

#### 1. Unit Tests

Test individual functions and methods in isolation:

```python
# Example: Backend unit test
def test_calculate_waste_fee():
    from backend.utils import calculate_fee
    
    result = calculate_fee(weight=100, waste_type="SW305")
    assert result > 0
    assert result == expected_value
```

```typescript
// Example: Frontend unit test
import { formatDate } from '@/lib/utils'

test('formatDate handles null input', () => {
  expect(formatDate(null)).toBe('N/A')
})
```

#### 2. Integration Tests

Test how components work together:

```python
# Example: Backend integration test
async def test_create_and_fetch_batch():
    # Create a batch
    response = await client.post("/api/v1/compliance/sw-batches", json=batch_data)
    assert response.status_code == 200
    batch_id = response.json()["id"]
    
    # Fetch the batch
    response = await client.get(f"/api/v1/compliance/sw-batches/{batch_id}")
    assert response.status_code == 200
    assert response.json()["id"] == batch_id
```

#### 3. E2E Tests

Test complete user flows:

```typescript
// Example: E2E test
test('user can create scheduled waste batch', async ({ page }) => {
  await page.goto('/compliance/scheduled-waste')
  await page.click('button:has-text("New Batch")')
  await page.fill('#sw-code', 'SW305')
  await page.fill('#quantity', '100')
  await page.click('button:has-text("Create")')
  await expect(page.locator('.success-message')).toBeVisible()
})
```

### Coverage Goals by Module

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| Authentication | ~30% | 90% | High |
| Compliance | ~20% | 80% | High |
| Jobs | ~15% | 75% | High |
| Recyclables | ~20% | 75% | Medium |
| Destruction | ~15% | 70% | Medium |
| Invoicing | ~10% | 70% | Medium |
| AI/RAG | ~25% | 60% | Low |
| Frontend Components | ~5% | 60% | Medium |

### Writing New Tests

#### Backend Test Template

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.mark.asyncio
async def test_endpoint_name(client: AsyncClient, db: AsyncSession):
    # Arrange: Set up test data
    test_data = {"field": "value"}
    
    # Act: Call the endpoint
    response = await client.post("/api/v1/endpoint", json=test_data)
    
    # Assert: Verify results
    assert response.status_code == 200
    data = response.json()
    assert data["field"] == "value"
```

#### Frontend Test Template

```typescript
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'

describe('ComponentName', () => {
  it('renders correctly', () => {
    render(<ComponentName prop="value" />)
    expect(screen.getByText('expected text')).toBeInTheDocument()
  })

  it('handles user interaction', async () => {
    const user = userEvent.setup()
    render(<ComponentName />)
    
    await user.click(screen.getByRole('button'))
    expect(screen.getByText('result')).toBeInTheDocument()
  })
})
```

### Test Organization

```
backend/
├── tests/
│   ├── unit/
│   │   ├── test_auth.py
│   │   ├── test_compliance.py
│   │   └── test_utils.py
│   ├── integration/
│   │   ├── test_api_endpoints.py
│   │   └── test_database.py
│   └── e2e/
│       └── test_workflows.py

frontend/
├── src/
│   ├── components/
│   │   └── __tests__/
│   │       └── ComponentName.test.tsx
│   ├── lib/
│   │   └── __tests__/
│   │       └── utils.test.ts
│   └── app/
│       └── __tests__/
│           └── page.test.tsx
```

## Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=. --cov-report=xml
      - uses: codecov/codecov-action@v3

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm test -- --coverage
```

## Test Data Management

### Fixtures

Use pytest fixtures for test data:

```python
@pytest.fixture
async def sample_client(db: AsyncSession):
    client = Client(
        company_name="Test Client",
        industry_vertical="Manufacturing",
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client
```

### Test Database

Use a separate test database:

```bash
# .env.test
DATABASE_URL=postgresql://hitech:test@localhost:5432/hitech_waste_test
```

## Mocking External Services

```python
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_with_mocked_external_service():
    # Mock Ollama
    with patch('backend.ai.ollama.chat', new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = {"response": "test"}
        
        # Test code that uses Ollama
        result = await call_ai_function()
        
        # Verify mock was called
        mock_chat.assert_called_once()
```

## Best Practices

1. **Test behavior, not implementation** - Focus on what the code does, not how
2. **Keep tests independent** - Each test should run in isolation
3. **Use descriptive test names** - `test_user_cannot_login_with_invalid_credentials`
4. **Arrange-Act-Assert pattern** - Structure tests clearly
5. **Mock external dependencies** - Don't test third-party services
6. **Test edge cases** - Empty inputs, null values, boundary conditions
7. **Keep tests fast** - Unit tests should run in milliseconds
8. **Use factories for test data** - Create reusable test data builders

## Coverage Tools

### Backend

```bash
# Install
pip install pytest-cov pytest-cov-report

# Run with detailed report
pytest --cov=. --cov-report=html --cov-report=term-missing --cov-report=xml
```

### Frontend

```bash
# Vitest has built-in coverage
npm test -- --coverage --coverage.reporter=html
```

## Monitoring Coverage

Set up coverage badges in README:

```markdown
![Backend Coverage](https://img.shields.io/badge/coverage-60%25-yellow)
![Frontend Coverage](https://img.shields.io/badge/coverage-40%25-red)
```

## Next Steps

1. **Run coverage report** to establish baseline
2. **Identify untested critical paths** (auth, core business logic)
3. **Write tests for high-priority areas** first
4. **Set up CI/CD** to run tests on every PR
5. **Enforce coverage gates** in CI (e.g., require 70% to merge)
6. **Regularly review coverage** and add tests for new features
7. **Refactor code** to make it more testable if needed

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Vitest Documentation](https://vitest.dev/)
- [Playwright Documentation](https://playwright.dev/)
- [Testing Best Practices](https://testingjavascript.com/)
