# XXE (XML External Entity)

Inject XML external entities that get processed by the XML parser.

## Dnslog Verification

Construct HTTP requests containing malicious XML that causes the **target server's XML parser** to resolve external entities, triggering DNS queries or HTTP requests to an OOB domain.

> See [DNS Log Verification](../verification/dnslog.md) for workflow and validation.

## Response Regex Verification

Construct HTTP requests containing malicious XML that causes the **target server's XML parser** to resolve external entities and include local file content, match against regex pattern.

> See [Regex Verification](../verification/regex.md) for workflow and validation.
