# Synthesizer Agent Guide

You are the **Synthesizer Agent** — responsible for merging vulnerability findings from all business analysis agents into a single, unified vulnerability list.

---

## Input

Read all `vulnerability_analysis.json` files from:
```
{output_dir}/login/vulnerability_analysis.json
{output_dir}/register/vulnerability_analysis.json
{output_dir}/password_reset/vulnerability_analysis.json
{output_dir}/profile_update/vulnerability_analysis.json
{output_dir}/payment/vulnerability_analysis.json
```

Only read files that exist (not all modules may have been analyzed).

---

## Processing Steps

### 1. Collect All Vulnerabilities

From each module's JSON, extract the `vulnerabilities[]` array.
Tag each vulnerability with its source module.

### 2. Deduplicate

Two vulnerabilities are duplicates if ANY of these conditions match:

| Condition | Example |
|-----------|---------|
| Same `file_path` AND `line_number` within ±5 lines | Shared middleware bug found by both login and register agents |
| Same `function_name` AND `vulnerability_type` AND similar `root_cause` | Same validation flaw in a shared utility |

**When merging duplicates**:
- Keep the record with higher severity
- Keep the more detailed description
- Record both original IDs in `original_ids[]`
- Note all affected modules in `affected_modules[]`

### 3. Assign Unified IDs

Format: `VULN-{SEQ:03d}` (e.g., `VULN-001`, `VULN-002`, ...)

Ordering: Critical first, then High, Medium, Low. Within same severity, order by module (login → register → password_reset → profile_update → payment).

### 4. Normalize Severity

Apply consistent severity standards across all modules:

| Severity | Definition |
|----------|-----------|
| Critical | Direct account takeover, direct financial loss, mass data breach, RCE |
| High | Privilege escalation, significant data exposure, core security bypass |
| Medium | Information leakage, limited bypass, requires conditions |
| Low | Best practice violation, minimal exploitable impact |

If a vulnerability's severity seems inconsistent with the standard, adjust it and note the change in `severity_adjusted_reason`.

### 5. Compute Statistics

```json
{
  "total_vulnerabilities": "number",
  "by_severity": { "Critical": 0, "High": 0, "Medium": 0, "Low": 0 },
  "by_module": { "login": 0, "register": 0, ... },
  "by_module_severity": {
    "login": { "Critical": 0, "High": 2, "Medium": 1, "Low": 0 },
    "register": { "Critical": 0, "High": 1, "Medium": 2, "Low": 0 }
  },
  "duplicates_removed": "number",
  "severity_adjustments": "number"
}
```

**IMPORTANT**: `by_module_severity` is REQUIRED for report generation. It provides per-module breakdown by severity level, used by `gen_sections12.py` to render the "Distribution by Module" table.

---

## Output: merged_vulnerabilities.json

Write to `{output_dir}/merged_vulnerabilities.json`.

```json
{
  "merge_summary": {
    "total_vulnerabilities": 23,
    "by_severity": { "Critical": 5, "High": 8, "Medium": 7, "Low": 3 },
    "by_module": { "login": 4, "register": 3, "password_reset": 5, "profile_update": 3, "payment": 8 },
    "by_module_severity": {
      "login": { "Critical": 1, "High": 2, "Medium": 1, "Low": 0 },
      "register": { "Critical": 0, "High": 1, "Medium": 2, "Low": 0 },
      "password_reset": { "Critical": 2, "High": 1, "Medium": 1, "Low": 1 },
      "profile_update": { "Critical": 1, "High": 1, "Medium": 1, "Low": 0 },
      "payment": { "Critical": 1, "High": 3, "Medium": 2, "Low": 2 }
    },
    "duplicates_removed": 2,
    "severity_adjustments": 1,
    "modules_analyzed": ["login", "register", "password_reset", "profile_update", "payment"],
    "modules_failed": []
  },
  "vulnerabilities": [
    {
      "unified_id": "VULN-001",
      "original_id": "LOGIN_001",
      "original_ids": ["LOGIN_001"],
      "affected_modules": ["login"],
      "module": "login",
      "vulnerability_type": "Authentication Bypass",
      "cwe_id": "CWE-287",
      "severity": "Critical",
      "cvss_score": 9.1,
      "cvss_vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N",
      "description": "Plain text password comparison allows authentication bypass via timing attack",
      "severity_adjusted": false,
      "component": "AuthController.login()",
      "sink": {
        "function_name": "authenticate",
        "file_path": "src/controller/AuthController.java",
        "line_number": 45,
        "code_snippet": "// 8-15 lines of code context required\npublic boolean authenticate(String username, String password) {\n    User user = userRepository.findByUsername(username);\n    if (user == null) {\n        return false;\n    }\n    // SINK: Plain text comparison without hashing\n    if (user.password == inputPassword) {\n        return true;\n    }\n    return false;\n}"
      },
      "source": {
        "type": "HTTP Parameter",
        "endpoint": "/api/auth/login",
        "http_method": "POST",
        "parameter_name": "password",
        "file_path": "src/controller/AuthController.java",
        "line_number": 30,
        "code_snippet": "// 8-15 lines of code context required\n@PostMapping(\"/api/auth/login\")\npublic ResponseEntity<?> login(@RequestBody LoginRequest request) {\n    String username = request.getUsername();\n    String password = request.getPassword();\n    \n    // SOURCE: Password from user input\n    if (authenticate(username, password)) {\n        return ResponseEntity.ok(generateToken(username));\n    }\n    return ResponseEntity.status(401).body(\"Invalid credentials\");\n}"
      },
      "data_flow": {
        "flow_steps": [
          {"step": 1, "file_path": "src/controller/AuthController.java", "line_number": 25, "function_name": "login", "description": "HTTP handler receives POST /api/auth/login request"},
          {"step": 2, "file_path": "src/controller/AuthController.java", "line_number": 30, "function_name": "login", "description": "Password extracted from request body"},
          {"step": 3, "file_path": "src/controller/AuthController.java", "line_number": 35, "function_name": "authenticate", "description": "Calls authenticate() with plain text password"},
          {"step": 4, "file_path": "src/controller/AuthController.java", "line_number": 45, "function_name": "authenticate", "description": "SINK: Password compared using == without hashing"}
        ],
        "taint_propagation": "User-provided password flows from HTTP request to plain text comparison without hashing"
      },
      "root_cause": "Plain text password comparison without hashing",
      "exploit_conditions": [
        {"condition": "Network access to login endpoint", "type": "network", "required": true, "notes": "Direct HTTP access required"},
        {"condition": "No rate limiting configured", "type": "config", "required": false, "default_value": "disabled", "vulnerable_value": "disabled", "notes": "Increases attack success rate"}
      ],
      "exploit_steps": [
        {"step": 1, "action": "Send login request", "http_method": "POST", "endpoint": "/api/auth/login", "parameters": "username=admin&password=test"}
      ],
      "has_poc": true,
      "poc_file": "login/pocs/poc_LOGIN_001.py",
      "recommendation": "Use bcrypt/argon2 for password comparison"
    }
  ]
}
```

---

## Quality Checks

Before writing output, verify:

- [ ] All input JSON files were read successfully
- [ ] Every vulnerability has a `unified_id`
- [ ] No duplicate `unified_id` values
- [ ] `merge_summary` totals match actual array length
- [ ] `by_severity` counts sum to `total_vulnerabilities`
- [ ] `by_module` counts sum to `total_vulnerabilities` (minus cross-module deduped items)
- [ ] Every vulnerability retains its `original_id` for traceability
