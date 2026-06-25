# Testing Rules

- **Zero DB Side-effects**: Tests must use a separate test database or mock database sessions. Always roll back transactions.
- **Isolate Tests**: Test cases must run independently of each other. Never rely on test execution order.
- **Mock Externals**: Do not make real API calls to Slack, GitHub, or LLMs during unit tests. Use `unittest.mock` or `pytest-mock`.
- **Target Coverage**: Aim for at least 80% coverage. Write assertions that verify fields, status codes, and headers.
- **Descriptive Names**: Name test functions clearly, describing the exact condition being tested (e.g. `test_create_task_invalid_payload_fails`).
