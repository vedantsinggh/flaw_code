# Database Systems Verification Checklist

- [ ] Indexed frequently scanned query fields.
- [ ] Avoided N+1 select queries by loading child dependencies eagerly.
- [ ] Stored data operations inside database transaction scopes.
