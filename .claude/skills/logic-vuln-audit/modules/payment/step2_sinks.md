# Payment SINK Detection Guide

Analyze payment code against predefined SINK points to detect business logic vulnerabilities.

**Input**: `payment/business_logic.json` from Step 1 + `payment_sinks_library.md` (SINK definitions)

---

## Detection Overview

Payment SINK detection uses a **3-phase approach**:

```
Phase 1: SINK Matching       -- Map identified scenarios to applicable SINKs
Phase 2: Workflow Deep Analysis -- Analyze each SINK against actual code
Phase 3: Vulnerability Confirmation -- Confirm findings with evidence
```

---

## Phase 1: SINK Matching

### Matching Rules

1. **Scenario-Specific SINKs**: Match each `scenario_id` from `business_logic.json` to its corresponding SINK category in `payment_sinks_library.md`
   - Example: `scenario_id=1` (E-Commerce) maps to Category 1 SINKs (5 SINKs)
   - Example: `scenario_id=10` (Marketing/Points) maps to Category 10 SINKs (4 SINKs)

2. **Universal SINKs**: ALL identified scenarios must also be checked against the 6 cross-scenario universal SINK categories:
   - Payment Callback Verification (4 SINKs)
   - Order State Machine (3 SINKs)
   - Amount Calculation & Precision (4 SINKs)
   - Concurrency/Duplicate Control (4 SINKs)
   - Authorization & Privilege (3 SINKs)
   - Data Validation (3 SINKs)

### Building the SINK Checklist

```
total_sinks = []
FOR each scenario in identified_scenarios:
    Add all SINKs from matching scenario category
    Add all 21 universal SINKs
    Deduplicate (some universal SINKs overlap with scenario SINKs)
```

**CRITICAL**: Do NOT skip any SINK. Every SINK in the library must be evaluated for every applicable scenario. Review the checklist three times before proceeding.

---

## Phase 2: Workflow Deep Analysis

For each matched SINK, analyze the relevant workflow code across **5 dimensions**.

### Dimension 1: Data Source Tracking

Trace where critical parameters originate:

| Source | Risk Level | Examples |
|--------|-----------|---------|
| Frontend/client parameters | HIGH | Price, quantity, amount, discount, coupon_id |
| Database query result | LOW | Price from product table, balance from account table |
| Server-side config | LOW-MEDIUM | Check if config is tamper-proof |
| Session/JWT claims | MEDIUM | User ID, role -- verify extraction method |
| External API response | MEDIUM | Payment gateway callback data |

**Key question**: Are critical values (price, amount, quantity, status) taken from trusted sources (database/config) or untrusted sources (client input)?

### Dimension 2: Calculation Logic Verification

Check whether financial calculations are correct and secure:

- Is the backend independently recalculating amounts (not trusting frontend)?
- Are there validation checks after calculation (non-negative, within limits)?
- Are edge cases handled (zero quantity, max integer, floating point)?
- Is the calculation order correct (discounts applied properly)?
- Are currency precision rules followed (integer cents vs floating point)?

### Dimension 3: Concurrency Control

Check for race conditions in payment operations:

- Are database transactions used for critical operations?
- Are locks used (row locks, distributed locks, optimistic locking)?
- Is there a time window between check and execution (TOCTOU)?
- Are atomic operations used for balance/inventory updates?
- Is there idempotency protection on payment endpoints?

### Dimension 4: Permission Verification

Check for authorization flaws:

- Is resource ownership verified (order belongs to current user)?
- Is user ID taken from session (not from request parameters)?
- Are admin-only operations properly gated?
- Can order IDs be enumerated/predicted?
- Are API endpoints properly authenticated?

### Dimension 5: Business Rule Validation

Check that business constraints are enforced:

- Does the state machine enforce valid transitions only?
- Are business constraints checked server-side (not just client)?
- Are error/exception paths handled securely?
- Are rollback operations correct (refund, cancel, return)?
- Are time-based rules enforced (expiration, cooling periods)?

---

## Phase 3: Vulnerability Confirmation

For each detected issue, apply strict confirmation criteria.

### Confirmed Vulnerability

A finding is confirmed when:
- Specific code defect is located (file + function + line)
- The defect can lead to a concrete security impact
- Exploitability is assessed (complexity, prerequisites)
- Code context is provided showing the flaw

### Not a Vulnerability

Do NOT flag if:
- Security control exists but is in a different file (trace it first)
- Framework provides built-in protection that covers this case
- The code snippet is incomplete -- mark as `needs_review` instead
- Theoretical risk only with no practical exploit path

### Severity Definitions

| Severity | Payment Context |
|----------|----------------|
| **Critical** | Direct financial loss, bypass payment entirely, steal funds, mass exploitation |
| **High** | Partial financial loss, privilege escalation, business logic bypass |
| **Medium** | Minor business impact, requires specific conditions, limited scope |

---

## Output

Write `vulnerability_analysis.json` following the **Payment Extended Schema** in `@reference/JSON_SCHEMAS.md` § vulnerability_analysis.json.

**CRITICAL — Field Name Compliance**:

Payment uses the **same core fields** as the Standard Schema, plus payment-specific extensions. You MUST use **exactly** these field names (not alternatives):

| Required Field | ❌ Do NOT Use |
|---|---|
| `vulnerability_id` | `id`, `vuln_id` |
| `vulnerability_type` | `title`, `vuln_name` |
| `sink` (dict with `file_path`, `function_name`, `line_number`, `code_snippet`) | `affected_files`, `affected_code`, `vulnerable_code` |
| `source` (dict with `file_path`, `endpoint`, `line_number`, `code_snippet`) | (do not omit) |
| `data_flow` (dict with `flow_steps[]`) | `taint_path` as sole format |
| `exploit_conditions` (list of **detailed objects**) | `exploit_complexity` (single string), simple string list |
| `recommendation` | `remediation`, `fix` |
| `scan_summary` (top-level) | `analysis_summary` |
| `cvss_score` (number, CVSS 4.0 base score, 0.0-10.0) | string format like `"7.5"` |

**Payment-specific extra fields** (in addition to standard fields):
- `scenario_id`, `scenario_name`, `workflow_id` — scenario context
- `sink_type` (`"business"` or `"universal"`) — SINK library classification
- `sink_category` — SINK library category name
- `impact` — specific financial/business impact description
- `missing_controls` — list of missing security controls

**ID format**: `PAY_001`, `PAY_002`, ... (prefix `PAY_` + 3-digit sequence).

**Additional output sections** (after `vulnerabilities[]`):
- `workflow_analysis[]` — per-workflow security assessment with `security_score` and `risk_level`

---

## 🔴 Enhanced Output Requirements

### 1. Code Snippet Requirements (8-15 lines)

For both `sink.code_snippet` and `source.code_snippet`:
- **Minimum 8 lines, maximum 15 lines** of code context
- Include the **function signature** (func/method declaration)
- Include **relevant logic** around the vulnerable operation
- Show **parameter handling** and **security-relevant code paths**

### 2. Call Stack Requirements (data_flow.flow_steps[])

**MANDATORY**: Every vulnerability MUST include a complete call stack from SOURCE to SINK.

Each `flow_steps` entry requires:
- `step`: Sequential number (1, 2, 3, ...)
- `file_path`: Relative path to the file
- `function_name`: Function/method name at this step
- `line_number`: Line number in the file
- `description`: ~50 chars explaining what happens at this step

**Example**:
```json
"data_flow": {
  "flow_steps": [
    {"step": 1, "file_path": "src/controllers/PaymentController.java", "function_name": "processPayment", "line_number": 50, "description": "HTTP handler receives payment request"},
    {"step": 2, "file_path": "src/controllers/PaymentController.java", "function_name": "processPayment", "line_number": 65, "description": "Reads amount from client request body"},
    {"step": 3, "file_path": "src/services/PaymentService.java", "function_name": "createOrder", "line_number": 120, "description": "Creates order with client-provided amount"},
    {"step": 4, "file_path": "src/services/PaymentService.java", "function_name": "createOrder", "line_number": 130, "description": "Sends to payment gateway WITHOUT server-side verification"}
  ],
  "taint_propagation": "Client-provided amount flows directly to payment gateway without server-side price validation"
}
```

### 3. Description & Recommendation Length (~100 chars)

- `description`: **80-120 characters** — detailed summary with security impact
- `recommendation`: **80-120 characters** — specific fix with code changes or configuration

### 4. Exploit Conditions Requirements (DETAILED FORMAT)

**MANDATORY**: Every vulnerability MUST include detailed exploit conditions as objects, NOT simple strings.

Each `exploit_conditions` entry requires:
- `condition`: The exploit condition description (≤80 chars)
- `type`: One of `config`, `permission`, `network`, `environment`, `user_action`, `timing`
- `required`: Boolean - `true` if mandatory for exploitation, `false` if optional
- `default_value`: For `config` type - the current/default value in the codebase
- `vulnerable_value`: For `config` type - the value needed for vulnerability to be exploitable
- `notes`: Additional context (e.g., "Enabled by default in v2.0")

**Example**:
```json
"exploit_conditions": [
  {
    "condition": "Server-side price validation is disabled",
    "type": "config",
    "required": true,
    "default_value": "disabled",
    "vulnerable_value": "disabled",
    "notes": "Price validation not implemented in payment flow"
  },
  {
    "condition": "Attacker has valid user session",
    "type": "permission",
    "required": true,
    "notes": "Any authenticated user can attempt exploitation"
  },
  {
    "condition": "Payment gateway accepts client-provided amount",
    "type": "environment",
    "required": true,
    "notes": "Gateway does not verify amount against merchant records"
  }
]
```

---

## Analysis Principles

1. **Depth over breadth**: Do not stop at function signatures -- trace the full implementation
2. **Follow the data**: Track every critical parameter from source to sink
3. **Consider the attacker**: Think about real exploit scenarios, not just theoretical flaws
4. **Precise locations**: Every finding must point to exact file, function, and line range
5. **No false positives**: Verify that security controls are truly absent, not just in another file
6. **No false negatives**: Check every SINK checkpoint -- do not skip any
7. **Cross-reference globals**: Middleware, filters, and interceptors may provide controls not visible in the handler
8. **Framework awareness**: Understand what the framework handles automatically (CSRF, prepared statements, etc.)
