# FastAPI Coding Rules

- **Use Async Endpoints**: Always define path operations with `async def` unless blocking synchronous library calls are strictly required (and cannot be run in threadpools).
- **Strict Typing**: Use Python type hints on all function arguments, return values, and variables.
- **Pydantic Validation**: Never parse request bodies manually. Always use Pydantic models. Use `Field` with descriptive validation and examples.
- **Dependency Injection**: Utilize `Depends()` for database sessions, authentication, and external services to facilitate unit testing.
- **Handle Exceptions Cleanly**: Throw `HTTPException` with specific status codes. Define global exception handlers for unhandled errors.
- **Response Models**: Always define a `response_model` or type annotation on path operations to prevent sensitive data leakage.
