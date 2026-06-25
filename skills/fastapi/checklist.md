# FastAPI Verification Checklist

- [ ] All new endpoints have structured Pydantic input/output schemas.
- [ ] Endpoints handle edge cases and throw appropriate HTTP status codes (400, 404, 422, etc.).
- [ ] Security dependencies (auth, token validation) are verified and applied.
- [ ] Unit tests cover both success and error paths.
- [ ] Swagger/OpenAPI documentation is updated and contains correct descriptions.
- [ ] Any database migration scripts are generated and checked.
