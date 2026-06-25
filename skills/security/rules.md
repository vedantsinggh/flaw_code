# Security Rules

- **No Hardcoded Secrets**: Under no circumstances should passwords, API keys, webhook URLs, or tokens be written directly in code. Use environment variables.
- **Input Sanitization**: Always validate and sanitize user inputs. Prevent raw string execution or raw SQL queries; use ORM methods or parameterized queries.
- **Safe Execution**: Never use `shell=True` in `subprocess.run` or `os.system` with untrusted inputs. Prefer native Python APIs over calling system shell commands.
- **Safe Paths**: Protect against Path Traversal by checking that paths are within the intended directory boundaries (e.g. using `os.path.abspath` and verifying the prefix).
- **Secure Authentication**: Ensure APIs use standardized auth headers (e.g. Bearer OAuth2) and cookies have secure flags set.
