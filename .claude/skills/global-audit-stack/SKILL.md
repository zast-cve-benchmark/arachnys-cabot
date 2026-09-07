---
name: global-audit-stack
description: Framework-specific global security audit. Reads the reference for the framework specified in the Agent prompt (LANGUAGE + FRAMEWORK), then audits the project according to that framework's known sinks, anti-patterns, and unsafe defaults. Dispatched by global-audit per recognized framework.
---

# global-audit-stack

You are a framework-specific auditor. The Agent prompt provides:

```
LANGUAGE:  <e.g. java>
FRAMEWORK: <e.g. shiro>
```

## Steps

1. Read `references/<LANGUAGE>/<FRAMEWORK>.md`. This file is your expert knowledge for this framework's configuration surface — its known sinks, recommended audit ordering, typical misuse patterns, safe defaults.

2. Audit the project per that reference's guidance. Apply the standard anti-hallucination rules (same as the foundation sub-skills):
   - Read files before reporting on them
   - Quote actual code in findings
   - Better to miss than to false-positive
   - Trace each finding to specific file paths + line numbers + affected endpoints (cross-reference `.discovered_endpoints.txt` if it exists)

3. Output findings to `OUTPUT_FILE` per the **Output format** section below.

## Output format

Write findings as a flat JSON array `[ {...}, ... ]` of `SimpleVulnInfo`. See `record-vulnerabilities` for the schema and the mandatory `validate_vulns.py` step. Empty findings → write `[]` (still valid).

## Enumeration discipline

When a reference says "enumerate every X" (e.g. every entry in a Shiro `filterChainDefinitions` block), be exhaustive. Many real-world misconfigurations are repeated patterns in the same config section — finding one entry is not finding the rest.

## No per-endpoint issues

Focus on GLOBAL or framework-configuration defects. Per-endpoint issues belong to audit-endpoint, not here.
