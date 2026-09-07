# Unsafe Database Connection

Exploit JDBC connection string injection vulnerabilities to read arbitrary files from the target system via MySQL LOAD DATA LOCAL INFILE.

## JDBC Verification

Construct HTTP requests that send **malicious JDBC URLs** to the target. When the target connects to the fake MySQL server, the server reads local files from the target.

> See [JDBC Connection Verification](../verification/jdbc.md) for workflow and validation.

## Common Scenarios

- JDBC URL parameter injection
- Connection string manipulation
- SSRF via JDBC connectors

## Key Points

1. Use `jdbc` verification method
2. Target must use vulnerable MySQL connector
3. Default reads `/etc/passwd` to confirm file access
