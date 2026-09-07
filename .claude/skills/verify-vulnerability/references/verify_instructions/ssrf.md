# SSRF (Server-Side Request Forgery)

Inject malicious URLs to make the target server send requests to internal services or external systems.

## Response Regex Verification

Construct HTTP requests containing `file://` URLs that cause the **target server** to read local files via SSRF, match output against regex pattern to confirm file content.

> See [Regex Verification](../verification/regex.md) for workflow and validation.

## Dnslog Verification

Construct HTTP requests that cause the **target server** to make outbound requests (DNS queries or HTTP requests) to an OOB domain.

> See [DNS Log Verification](../verification/dnslog.md) for workflow and validation.
