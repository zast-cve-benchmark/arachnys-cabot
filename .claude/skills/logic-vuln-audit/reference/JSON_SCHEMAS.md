# JSON Output Schemas

All JSON schemas used by the logic-vuln-skill agents.

---

## 🔴 QUICK REFERENCE: Complete Vulnerability Entry Template

**Copy this template when creating each vulnerability entry. Fill in ALL fields.**

```json
{
  "vulnerability_id": "LOGIN_001",
  "vulnerability_type": "Insufficient Brute Force Protection",
  "cwe_id": "CWE-307",
  "severity": "Medium",
  "cvss_score": 5.3,
  "cvss_vector": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:L/VA:N/SC:N/SI:N/SA:N",
  "description": "Login rate limiting uses 1.5s lockout per failure, allowing ~40 attempts/min. Distributed attacks bypass in-memory lock storage.",
  "component": "auth.Lock",
  "sink": {
    "file_path": "src/core/auth/lock.go",
    "line_number": 33,
    "function_name": "Lock",
    "code_snippet": "package auth\n\nimport (\n\t\"sync\"\n\t\"time\"\n)\n\nconst frozenTime time.Duration = 1500 * time.Millisecond\n\ntype UserLock struct {\n\tmu        sync.Mutex\n\tfrozenAt  time.Time\n}"
  },
  "source": {
    "type": "HTTP Parameter",
    "endpoint": "POST /c/login",
    "http_method": "POST",
    "parameter_name": "principal",
    "file_path": "src/core/controllers/base.go",
    "line_number": 76,
    "code_snippet": "func (cc *CommonController) Login() {\n\tprincipal := cc.GetString(\"principal\")\n\tpassword := cc.GetString(\"password\")\n\t\n\tuser, err := auth.Login(cc.Ctx.Request.Context(), models.AuthModel{\n\t\tPrincipal: principal,\n\t\tPassword:  password,\n\t})\n}"
  },
  "data_flow": {
    "flow_steps": [
      {"step": 1, "file_path": "src/core/controllers/base.go", "function_name": "Login", "line_number": 76, "description": "HTTP handler receives login credentials"},
      {"step": 2, "file_path": "src/core/auth/authenticator.go", "function_name": "Login", "line_number": 137, "description": "Calls auth.Login() with credentials"},
      {"step": 3, "file_path": "src/core/auth/lock.go", "function_name": "Lock", "line_number": 45, "description": "Checks lock status with 1.5s timeout"},
      {"step": 4, "file_path": "src/core/auth/lock.go", "function_name": "Lock", "line_number": 33, "description": "SINK: frozenTime constant = 1500ms"}
    ],
    "taint_propagation": "Login attempt triggers lock check with insufficient timeout duration"
  },
  "root_cause": "Lock timeout (1.5s) is too short to prevent brute force attacks",
  "exploit_conditions": [
    {
      "condition": "Network access to login endpoint",
      "type": "network",
      "required": true,
      "notes": "Must be able to reach /c/login endpoint"
    },
    {
      "condition": "No additional CAPTCHA protection",
      "type": "config",
      "required": true,
      "default_value": "disabled",
      "vulnerable_value": "disabled",
      "notes": "CAPTCHA is not enabled by default"
    },
    {
      "condition": "No distributed lock storage in cluster",
      "type": "environment",
      "required": false,
      "default_value": "in-memory",
      "vulnerable_value": "in-memory",
      "notes": "Clustered deployments without shared Redis allow per-node bypass"
    }
  ],
  "exploit_steps": [
    {"step": 1, "action": "Send login request with wrong password", "http_method": "POST", "endpoint": "/c/login", "parameters": "principal=admin&password=wrong"},
    {"step": 2, "action": "Wait 1.6 seconds to bypass lock", "http_method": "", "endpoint": "", "parameters": ""},
    {"step": 3, "action": "Repeat with next password candidate", "http_method": "POST", "endpoint": "/c/login", "parameters": "principal=admin&password=next_guess"}
  ],
  "recommendation": "Implement exponential backoff (2^n seconds) and distributed lock storage (Redis) for clustered deployments",
  "poc_file": "pocs/poc_LOGIN_001.py"
}
```

**Field Validation Checklist:**

| Field | Validation Rule |
|-------|----------------|
| `vulnerability_id` | Pattern: `{PREFIX}_\d{3}` (e.g., `LOGIN_001`, `REG_001`) |
| `cvss_score` | Number (NOT string), range 0.0-10.0 |
| `cvss_vector` | Starts with `CVSS:4.0/` |
| `description` | 80-120 characters |
| `recommendation` | 80-120 characters |
| `sink.code_snippet` | 8-15 lines |
| `source.code_snippet` | 8-15 lines |
| `data_flow.flow_steps` | Array with ≥2 entries |

---

## § _session.json (Leader Output)

```json
{
  "project_name": "string",
  "project_path": "string (absolute path)",
  "language": "string (java|php|python|golang|nodejs)",
  "frameworks": {
    "web": ["string"],
    "orm": ["string"],
    "auth": ["string"],
    "other": ["string"]
  },
  "output_lang": "string (en|zh|ja)",
  "started_at": "string (ISO8601)",
  "discovered_functions": ["string"],
  "discovery_details": {
    "{function}": {
      "confidence": "number (0.0-1.0)",
      "entry_files": ["string (relative path)"]
    }
  },
  "batch_plan": [
    {
      "batch": "number",
      "agents": ["string"]
    }
  ],
  "errors": ["string (optional, logged failures)"]
}
```

---

## § business_logic.json (Business Agent Step 1 Output)

### Standard Schema (login, register, password_reset, profile_update)

```json
{
  "module": "string (login|register|password_reset|profile_update)",
  "project_language": "string",
  "project_framework": "string",
  "business_intent": "string (high-level description of what this function is designed to do)",
  "core_workflow": "string (brief description of the main flow)",
  "workflows": [
    {
      "workflow_id": "string (e.g. login_001)",
      "workflow_name": "string",
      "description": "string",
      "entry_point": {
        "file_path": "string",
        "function_name": "string",
        "http_method": "string (GET|POST|PUT|DELETE)",
        "route": "string (URL pattern)"
      },
      "global_components": [
        {
          "type": "string (middleware|filter|interceptor|decorator)",
          "name": "string",
          "file_path": "string",
          "purpose": "string"
        }
      ],
      "business_logic": [
        {
          "step": "number",
          "layer": "string (pre_processing|auth|business_logic|data_operation|response|async)",
          "description": "string",
          "file_path": "string",
          "function_name": "string",
          "line_range": "string (e.g. 45-67)",
          "security_relevant": "boolean"
        }
      ],
      "data_operations": [
        {
          "type": "string (db_read|db_write|cache_read|cache_write|file_io)",
          "description": "string",
          "file_path": "string",
          "function_name": "string",
          "table_or_key": "string"
        }
      ],
      "configurations": [
        {
          "name": "string",
          "value": "string",
          "file_path": "string",
          "security_impact": "string"
        }
      ],
      "external_calls": [
        {
          "service": "string",
          "purpose": "string",
          "file_path": "string"
        }
      ]
    }
  ]
}
```

### Payment Extended Schema

Payment uses the same schema but wraps workflows inside identified scenarios:

```json
{
  "module": "payment",
  "project_language": "string",
  "project_framework": "string",
  "business_intent": "string",
  "core_workflow": "string",
  "identified_scenarios": [
    {
      "scenario_id": "number (1-12)",
      "scenario_name": "string (e.g. e_commerce, subscription, financial_payment)",
      "confidence": "number (0.0-1.0)",
      "description": "string",
      "workflows": [
        {
          "workflow_id": "string (e.g. pay_ecom_001)",
          "...": "same as standard workflow schema above"
        }
      ]
    }
  ]
}
```

---

## § vulnerability_analysis.json (Business Agent Step 2 Output)

### Standard Schema (ALL business agents MUST use this exact schema)

**CRITICAL**: All 5 business agents (login, register, password_reset, profile_update, payment) MUST produce vulnerability_analysis.json with **exactly** this structure. The Synthesizer and Report Generator depend on consistent field names.

**Field Name Compliance Table** — use ONLY the left column names:

| ✅ Required Field | ❌ BANNED Alternatives |
|---|---|
| `vulnerability_id` (string) | `id`, `vuln_id` |
| `vulnerability_type` (string) | `title`, `vuln_name`, `sink_category` |
| `cvss_score` (number, float) | string format like `"7.5"` |
| `cvss_vector` (string) | (do not omit — must be valid CVSS 4.0 vector string) |
| `cwe_id` (string) | (do not omit — e.g. "CWE-287") |
| `description` (string, **~100 chars, 80-120 range**) | `summary`, `brief` |
| `sink` (dict) | `affected_files`, `affected_code`, `vulnerable_code` |
| `source` (dict) | (do not omit this field) |
| `data_flow` (dict with `flow_steps[]`) | (MANDATORY — must contain **complete call stack** from SOURCE to SINK with ≥2 steps) |
| `exploit_conditions` (list of **detailed objects** — see schema below) | `attack_scenario` (string), `exploit_complexity`, simple string list |
| `recommendation` (string, **~100 chars, 80-120 range**) | `remediation`, `fix` |
| `scan_summary` (top-level dict) | `analysis_summary`, bare `total_vulnerabilities` at top level |

**ID Prefix Convention**: `LOGIN_001`, `REG_001`, `PWD_001`, `PROF_001`, `PAY_001`.

```json
{
  "module": "string",
  "scan_summary": {
    "total_vulnerabilities": "number",
    "by_severity": { "Critical": 0, "High": 0, "Medium": 0, "Low": 0 },
    "scan_timestamp": "string (ISO8601)",
    "code_base_path": "string",
    "language": "string",
    "framework": "string"
  },
  "vulnerabilities": [
    {
      "vulnerability_id": "string (e.g. LOGIN_001, REG_001, PWD_001, PROF_001)",
      "vulnerability_type": "string (short name of the vulnerability)",
      "cwe_id": "string (e.g. CWE-287, CWE-640)",
      "severity": "string (Critical|High|Medium|Low)",
      "cvss_score": "number (CVSS 4.0 base score, 0.0-10.0)",
      "cvss_vector": "string (CVSS 4.0 vector, e.g. CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:N/SC:N/SI:N/SA:N)",
      "description": "string (**~100 characters, 80-120 range**, detailed vulnerability summary with security impact)",
      "component": "string (affected component/function)",
      "sink": {
        "function_name": "string (REQUIRED)",
        "class_name": "string",
        "file_path": "string (REQUIRED — relative path to vulnerable code)",
        "line_number": "number (REQUIRED)",
        "code_snippet": "string (REQUIRED — **8-15 lines** of code context around the dangerous operation)",
        "parameters": ["string"]
      },
      "source": {
        "type": "string (HTTP Parameter|Cookie|Header|URL Path|...)",
        "endpoint": "string (e.g. POST /api/user/signup)",
        "http_method": "string",
        "parameter_name": "string",
        "file_path": "string (REQUIRED — source entry file path)",
        "line_number": "number (REQUIRED)",
        "code_snippet": "string (REQUIRED — **8-15 lines** of code context around the entry point)"
      },
      "data_flow": {
        "flow_steps": [
          {
            "step": "number (REQUIRED — sequential step number starting from 1)",
            "file_path": "string (REQUIRED — relative path to file)",
            "function_name": "string (REQUIRED — function/method name at this step)",
            "line_number": "number (REQUIRED — line number in the file)",
            "description": "string (REQUIRED — **~50 chars**, what happens at this step)",
            "code_snippet": "string (optional — key line of code at this step)"
          }
        ],
        "taint_propagation": "string (description of how tainted data flows)",
        "_comment": "MANDATORY: flow_steps[] must contain COMPLETE call stack from SOURCE to SINK. Minimum 2 steps (entry point and vulnerable operation). Trace every function call in between."
      },
      "root_cause": "string",
      "exploit_conditions": [
        {
          "condition": "string (the exploit condition, ≤80 chars)",
          "type": "string (config|permission|network|environment|user_action|timing)",
          "required": "boolean (true if mandatory for exploitation)",
          "default_value": "string (optional — current/default value if this is a config)",
          "vulnerable_value": "string (optional — value needed for vulnerability to be exploitable)",
          "notes": "string (optional — additional context, e.g., 'Changed in v2.0')"
        }
      ],
      "exploit_steps": [
        {
          "step": "number",
          "action": "string (brief description of the step)",
          "http_method": "string (optional)",
          "endpoint": "string (optional)",
          "parameters": "string (optional)"
        }
      ],
      "recommendation": "string (**~100 characters, 80-120 range**, detailed fix suggestion with specific code changes or configuration)",
      "poc_file": "string (relative path to generated Python PoC, e.g. pocs/poc_LOGIN_001.py)"
    }
  ]
}
```

### Payment Extended Schema

Payment uses the **same standard schema** with additional fields. All standard fields (`vulnerability_id`, `vulnerability_type`, `sink`, `source`, `data_flow`, etc.) MUST use the same names and structures as above.

Additional payment-specific fields per vulnerability:

```json
{
  "module": "payment",
  "scan_summary": {
    "total_vulnerabilities": "number",
    "by_severity": { "Critical": 0, "High": 0, "Medium": 0, "Low": 0 },
    "by_scenario": {},
    "scan_timestamp": "string (ISO8601)",
    "code_base_path": "string",
    "language": "string",
    "framework": "string"
  },
  "vulnerabilities": [
    {
      "vulnerability_id": "string (e.g. PAY_001)",
      "vulnerability_type": "string",
      "severity": "string (Critical|High|Medium|Low)",
      "cvss_score": "number (CVSS 4.0 base score, 0.0-10.0)",
      "component": "string",
      "sink": { "...SAME as standard schema above..." },
      "source": { "...SAME as standard schema above..." },
      "data_flow": { "...SAME as standard schema above (flow_steps[])..." },
      "root_cause": "string",
      "exploit_conditions": [
        {
          "condition": "string (≤80 chars)",
          "type": "string (config|permission|network|environment|user_action|timing)",
          "required": "boolean",
          "default_value": "string (for config type)",
          "vulnerable_value": "string (for config type)",
          "notes": "string (optional)"
        }
      ],
      "recommendation": "string",

      "_comment": "--- Payment-specific extensions below ---",
      "scenario_id": "number",
      "scenario_name": "string",
      "workflow_id": "string",
      "sink_type": "string (business|universal)",
      "sink_category": "string (e.g. amount_tampering|callback_verification)",
      "impact": "string (specific financial/business impact)",
      "missing_controls": ["string"]
    }
  ],
  "workflow_analysis": [
    {
      "workflow_id": "string",
      "workflow_name": "string",
      "security_score": "number (0-100)",
      "risk_level": "string (Critical|High|Medium|Low)",
      "vulnerabilities_found": ["string (vulnerability IDs)"]
    }
  ]
}
```

---

## § poc_output (Business Agent Step 3 Output)

### poc_{ID}.json

```json
{
  "vuln_id": "string (e.g. LOGIN_001)",
  "vuln_info": {
    "type": "string",
    "severity": "string",
    "module": "string",
    "component": "string"
  },
  "vulnerability_description": {
    "summary": "string",
    "detail": "string",
    "root_cause": "string"
  },
  "exploitability_analysis": {
    "is_exploitable": "boolean",
    "difficulty": "string (Low|Medium|High)",
    "prerequisites": ["string"],
    "success_rate": "string",
    "side_effects": ["string"],
    "detection_likelihood": "string"
  },
  "exploitation_steps": [
    {
      "step": "number",
      "action": "string",
      "http_method": "string",
      "url": "string",
      "headers": {},
      "parameters": {},
      "expected_response": "string",
      "verification": "string"
    }
  ],
  "poc_code": "string (Python code, also saved as .py file)",
  "poc_file": "string (relative path to .py file)",
  "verification": {
    "success_indicators": ["string"],
    "failure_indicators": ["string"]
  },
  "fix": [
    {
      "recommendation": "string",
      "fixed_code": "string (optional)",
      "priority": "string (P0|P1|P2|P3)"
    }
  ]
}
```

---

## § merged_vulnerabilities.json (Synthesizer Output)

```json
{
  "merge_summary": {
    "total_vulnerabilities": "number",
    "by_severity": { "Critical": 0, "High": 0, "Medium": 0, "Low": 0 },
    "by_module": { "login": 0, "register": 0, "password_reset": 0, "profile_update": 0, "payment": 0 },
    "duplicates_removed": "number",
    "severity_adjustments": "number",
    "modules_analyzed": ["string"],
    "modules_failed": ["string"]
  },
  "vulnerabilities": [
    {
      "unified_id": "string (VULN-001)",
      "original_id": "string",
      "original_ids": ["string"],
      "affected_modules": ["string"],
      "module": "string (primary module)",
      "vulnerability_type": "string",
      "cwe_id": "string (e.g. CWE-287)",
      "severity": "string",
      "cvss_score": "number (CVSS 4.0 base score, 0.0-10.0)",
      "cvss_vector": "string (CVSS 4.0 vector string)",
      "description": "string (≤100 characters)",
      "severity_adjusted": "boolean",
      "severity_adjusted_reason": "string (optional)",
      "component": "string",
      "sink": {
        "file_path": "string",
        "line_number": "number",
        "function_name": "string",
        "code_snippet": "string"
      },
      "source": {
        "file_path": "string",
        "line_number": "number",
        "endpoint": "string",
        "code_snippet": "string"
      },
      "data_flow": {
        "flow_steps": ["...same as vulnerability_analysis.json..."]
      },
      "root_cause": "string",
      "exploit_conditions": ["...same detailed object format as vulnerability_analysis.json, OR legacy string list for backwards compatibility..."],
      "exploit_steps": ["...same as vulnerability_analysis.json..."],
      "has_poc": "boolean",
      "poc_file": "string (relative path)",
      "recommendation": "string (≤100 characters)"
    }
  ]
}
```

---

## § exploit_chains.json (Chain & Reporter Output)

> **🔴 MANDATORY FIELD NAME**: The field MUST be named `attack_flow` (not `exploit_steps`, `steps`, or any variant). The report generation script `gen_sections456.py` will fail if this field is incorrectly named.

```json
{
  "chain_summary": {
    "total_chains": "number",
    "by_severity": { "Critical": 0, "High": 0, "Medium": 0, "Low": 0 }
  },
  "chains": [
    {
      "chain_id": "string (CHAIN-001)",
      "chain_name": "string",
      "severity": "string",
      "score": "number (8-24)",
      "vulnerabilities_used": ["string (VULN-xxx IDs)"],
      "modules_involved": ["string"],
      "attack_flow": [
        {
          "step": "number",
          "action": "string",
          "vulnerability": "string (VULN-xxx)",
          "input": "string",
          "output": "string"
        }
      ],
      "prerequisites": ["string"],
      "impact": "string",
      "success_rate": "number (0.0-1.0)",
      "mitigation": ["string (which fix breaks the chain)"],
      "poc_file": "string (relative path)",
      "score_breakdown": {
        "prerequisites": "number (1-3)",
        "complexity": "number (1-3)",
        "automation": "number (1-3)",
        "reliability": "number (1-3)",
        "impact_scope": "number (1-3)",
        "detection": "number (1-3)",
        "persistence": "number (1-3)",
        "data_sensitivity": "number (1-3)",
        "notes": "string (optional, format: 'Key=N (explanation); Key=N (explanation)')"
      }
    }
  ]
}
```

### attack_flow Field Constraints

| Aspect | Required | ❌ Forbidden |
|--------|----------|--------------|
| **Field name** | `attack_flow` | `exploit_steps`, `steps`, `flow`, `attack_steps` |
| **Step object fields** | `step`, `action`, `vulnerability`, `input`, `output` | `http_method`, `endpoint`, `parameters`, `request_body`, `response` |
| **input/output values** | Abstract data description (`"Valid username"`, `"Session token"`) | HTTP implementation details (`"POST /api/login"`)
