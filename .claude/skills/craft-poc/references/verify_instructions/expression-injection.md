# Expression Injection

Inject expressions in template engines or expression languages (SpEL, OGNL, MVEL, etc.) that get evaluated by the web application.

## Dnslog Verification

Construct HTTP requests that cause the **target server** to evaluate injected expressions, which send DNS queries or HTTP requests to an OOB domain.

> See [DNS Log Verification](../verification/dnslog.md) for workflow and validation.

## Response Regex Verification

Inject expressions that cause the **target server** to read files or output data, match output against regex pattern.

> See [Regex Verification](../verification/regex.md) for workflow and validation.
