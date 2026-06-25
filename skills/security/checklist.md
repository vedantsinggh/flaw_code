# Security Verification Checklist

- [ ] Run `bandit` on the code and resolve all findings.
- [ ] Scan files for hardcoded secrets (API keys, webhook URLs).
- [ ] Verify that all user inputs are validated via Pydantic or type boundaries.
- [ ] Confirm no dynamic queries or SQL-string formatting is used.
- [ ] Verify no system-shell execution runs raw string payloads.
- [ ] Check dependencies for CVEs using `pip-audit`.
