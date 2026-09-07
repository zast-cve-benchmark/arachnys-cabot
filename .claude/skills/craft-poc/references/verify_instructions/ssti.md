# SSTI (Server-Side Template Injection)

Inject template-specific syntax that gets rendered server-side (Jinja2, Twig, Freemarker, etc.).

## Dnslog Verification

Construct HTTP requests that cause the **target server** to render injected template payloads, which send DNS queries or HTTP requests to an OOB domain.

> See [DNS Log Verification](../verification/dnslog.md) for workflow and validation.

## Response Regex Verification

Inject template payloads that cause the **target server** to read files or output data, match output against regex pattern.

> See [Regex Verification](../verification/regex.md) for workflow and validation.
