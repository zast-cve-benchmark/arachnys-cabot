---
name: craft-poc
description: Guide for crafting vulnerability verification PoCs (Proof of Concept) for specific web endpoints. Use this skill when you need to verify whether a specific vulnerability exists at a specific web endpoint and construct a PoC to validate it.
---

# Craft PoC

## Overview

This skill guides security researchers in writing vulnerability verification PoCs that comply with zast-verifier requirements. It ensures PoCs are structured correctly and can be validated by the verification framework.

## Prerequisites

**1. Define Target API Endpoint and Vulnerability Type**

Before writing any PoC, you MUST first determine:
- **Target API endpoint** - Which specific endpoint needs vulnerability verification
- **Vulnerability type** - What kind of vulnerability to test for (e.g., XSS, Command Injection, SQL Injection, etc.)

If the user has not provided the API endpoint, **ask the user**: 

> "Which API endpoint do you want to create a PoC for?"

If the user has not provided the vulnerability type, you should first examine the endpoint's source code to identify all potential security flaws, then verify each candidate vulnerability through testing to determine which ones are actually exploitable.

---

**2. You MUST obtain the API Base URL before writing any PoC.**

If not provided, **first check the current working directory for a `.env` file**. Look for these configurations:
- `TARGET_API_BASE` - The target API base URL
- `OXPK_SANDBOX_URL` - Alternative sandbox environment URL

If found, use that value as the API Base URL.

If no `.env` file exists or the configurations are not found, ask the user:

> "What is the API Base URL of the target web app?"

If the user is unsure, read [references/concepts/api-base-url.md](references/concepts/api-base-url.md) and explain.

## PoC Structure Specification

Use Python to craft PoC.

### Code Style

- Use `requests` library for HTTP requests
- Keep code flat, clean, and readable
- **No class-level encapsulation**
- Wrap into functions only when:
  - Constructing complex payloads
  - Sending requests to multiple different endpoints
- Main workflow goes under `if __name__ == "__main__":`
- Minimal, concise comments only

### PoC Elements

A PoC consists of:
1. **API Base URL** - The target service base address
2. **Endpoint** - The vulnerable API endpoint
3. **Authentication** - User credentials/headers (if required)
4. **Payload** - The malicious request payload

**Important**:
- If the user specifies a particular endpoint, only target that endpoint. Do not include other vulnerable endpoints even if discovered.
- Not all endpoints require authentication. Some are only accessible without login.

### Authentication & Authorization

For endpoints requiring authentication, load authentication data from the config module instead of hardcoding:

```python
import requests

from zast_verifier import config


if __name__ == '__main__':
  # Load pre-configured admin authentication
  admin_headers: dict[str, str] = config.get_admin_headers()
  admin_cookies: dict[str, str] = config.get_admin_cookies()
  
  ...
  
  # Use loaded credentials in requests
  response = requests.post(
      ...,
      headers=admin_headers,
      cookies=admin_cookies
  )
```

## Payload Picker

**When you cannot construct a working payload**, use the Payload Picker tool to get reference payloads for your vulnerability type.

### Usage

```bash
# List all supported vulnerability types
zast-payloads pick --list

# Get payloads for a specific vulnerability type
zast-payloads pick {vuln_type}
```

For detailed documentation, see [references/concepts/payload-picker.md](references/concepts/payload-picker.md).

## Vulnerability Verification Guide

| Type                 | Reference                                                                                     |
|----------------------|-----------------------------------------------------------------------------------------------|
| XSS                  | [xss.md](references/verify_instructions/xss.md)                                               |
| Command Injection    | [command-injection.md](references/verify_instructions/command-injection.md)                   |
| Code Injection       | [code-injection.md](references/verify_instructions/code-injection.md)                         |
| Expression Injection | [expression-injection.md](references/verify_instructions/expression-injection.md)             |
| SSTI                 | [ssti.md](references/verify_instructions/ssti.md)                                             |
| Deserialization      | [deserialization.md](references/verify_instructions/deserialization.md)                       |
| JNDI Injection       | [jndi.md](references/verify_instructions/jndi.md)                                             |
| Insecure DB Connection | [insecure-database-connection.md](references/verify_instructions/insecure-database-connection.md) |
| XXE                  | [xxe.md](references/verify_instructions/xxe.md)                                               |
| SSRF                 | [ssrf.md](references/verify_instructions/ssrf.md)                                             |
| Open Redirection     | [open-redirection.md](references/verify_instructions/open-redirection.md)                     |
| Path Traversal       | [path-traversal.md](references/verify_instructions/path-traversal.md)                         |
| Incorrect Signature Verification | [incorrect-signature-verification.md](references/verify_instructions/incorrect-signature-verification.md) |

## Verification Methods

| Method                  | Use Case                 | Reference                                                                        |
|-------------------------|--------------------------|----------------------------------------------------------------------------------|
| browser-alert           | XSS detection            | [browser-alert.md](references/verification/browser-alert.md)                     |
| dnslog                  | RCE-class, XXE           | [dnslog.md](references/verification/dnslog.md)                                   |
| regex                   | Data leakage             | [regex.md](references/verification/regex.md)                                     |
| jndi                    | JNDI/LDAP injection      | [jndi.md](references/verification/jndi.md)                                       |
| jdbc                    | JDBC SSRF/File read      | [jdbc.md](references/verification/jdbc.md)                                       |
| binary_deserialization  | Insecure deserialization | [deserialization.md](references/verification/deserialization.md)                 |

## Verification Requirement

**Verification is MANDATORY.**

You MUST run `zast-verifier validate-poc` to validate the PoC before writing it to any file, never write an unvalidated PoC to disk.

No matter how vulnerable an endpoint appears, it is **NOT** a valid vulnerability report until verified.

**Only `VERIFY_PASS` counts.** Any other result means the vulnerability is unconfirmed.

### CLI Usage

```bash
zast-verifier validate-poc -c "%poc_code%" --method <method> [options]
```
