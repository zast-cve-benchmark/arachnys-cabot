# Payload Picker

## Overview

When crafting PoCs for vulnerabilities, you may encounter difficulties constructing the correct payload for exploitation. The **Payload Picker** tool (`zast-payloads pick`) provides a database of reference payloads for various vulnerability types, helping you find working examples when you're stuck.

## When to Use

Use the Payload Picker when:
- You cannot construct a working payload from scratch
- You need reference examples for a specific vulnerability type
- You want to explore different payload variations for testing
- Your initial payload attempts failed verification

## Usage

### List All Supported Vulnerability Types

```bash
zast-payloads pick --list
```

This shows all available vulnerability types in the payload database.

### Get Payloads for a Specific Vulnerability Type

```bash
zast-payloads pick {vuln_type}
```

Replace `{vuln_type}` with the vulnerability type you need.

## Examples

### Example 1: Get XSS Payloads

```bash
zast-payloads pick xss
```

Output example:
```json
[
  {
    "payloads": [
      "<img src=1 onerror=alert(9)>",
      "\"><img src=1 onerror=alert(9)>",
      "\"><svg/onload=alert(9)>",
      "1\" onmouseover=alert(9)>",
      "'onmouseover='alert(9)'"
    ],
    "verify_method": "browser-pop-up",
    "placeholder": null,
    "pattern": null,
    "message": "9"
  },
  ...
]
```

### Example 2: Get Command Injection Payloads

```bash
zast-payloads pick command_injection
```

### Example 3: Get Specific Subtype Payloads

Some vulnerability types have subtypes:

```bash
zast-payloads pick command_injection/beanshell
```

## Output Format

Each payload entry contains:

| Field | Description |
|-------|-------------|
| `payloads` | List of payload strings to try |
| `verify_method` | Suggested verification method |
| `placeholder` | Placeholder to replace in your PoC |
| `pattern` | Regex pattern for verification (if applicable) |
| `message` | Expected message/value for verification |

## How to Use Payloads in PoC

1. **Run the picker command** to get reference payloads
2. **Select appropriate payloads** based on your target context:
   - Input field type (text, URL, etc.)
   - Injection context (inside HTML, JavaScript, attribute, etc.)
   - Character filtering/escaping
3. **Adapt payloads** to your specific endpoint:
   - Modify alert message numbers if needed
   - Adjust quotes/escaping for your context
   - Combine with your endpoint's parameter structure
4. **Test and iterate** - try different payloads until verification passes

## Important Notes

- **Reference Only**: These payloads are references. You may need to adapt them to your specific scenario.
- **Verification Required**: Always run `scripts/validate_poc.py` after constructing your PoC with picked payloads.
- **Message Numbers**: Some payloads use specific numbers (like `alert(9)`). The verification system expects these exact values.
- **Multiple Attempts**: If one payload doesn't work, try others from the list. Different contexts require different payload structures.

## Workflow Integration

Recommended workflow when stuck on payload construction:

```
1. Identify vulnerability type
2. zast-payloads pick --list          # Check available types
3. zast-payloads pick {vuln_type}     # Get reference payloads
4. Select and adapt payload           # Customize for your context
5. Construct PoC with payload
6. scripts/validate_poc.py {poc.py}   # Verify
7. If fails, try another payload from list
```

## Common Vulnerability Types

Some commonly used vulnerability types include:

- `xss` - Cross-Site Scripting
- `command_injection` - OS Command Injection
- `code_injection` - Code Injection
- `sql_injection` - SQL Injection
- `xxe` - XML External Entity
- `ssti` - Server-Side Template Injection
- `ssrf` - Server-Side Request Forgery
- `path_traversal` - Path/Directory Traversal
- `deserialization` - Insecure Deserialization

Use `zast-payloads pick --list` to see all available types.
