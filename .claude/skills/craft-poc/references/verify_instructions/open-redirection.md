# Open Redirection

Inject URLs that cause the server to redirect users to attacker-controlled destinations.

## Dnslog Verification

Construct HTTP requests containing malicious redirect destinations that cause the **target server** to redirect or callback to an OOB domain, triggering DNS queries or HTTP requests.

> See [DNS Log Verification](../verification/dnslog.md) for workflow and validation.

## Notes

- Open redirection vulnerabilities typically occur in redirect parameters (`url`, `redirect`, `return`, `next`, `callback`, `target`, etc.)
- Common bypasses include:
  - `@` trick: `http://legit.com@evil.com`
  - Protocol-relative: `//evil.com`
  - Path traversal: `/\\evil.com`
  - URL encoding: `%2f%2fevil.com`
  - Double slashes: `http://evil.com//legit.com`
