# Command Injection

Inject commands that get executed by the web application through shell invocation.

## Dnslog Verification

Construct HTTP requests that cause the **target server** to execute injected commands, which send DNS queries or HTTP requests to an OOB domain.

> See [DNS Log Verification](../verification/dnslog.md) for workflow and validation.

## Response Regex Verification

Inject commands that cause the **target server** to read local files or output data, match output against regex pattern.

> See [Regex Verification](../verification/regex.md) for workflow and validation.
