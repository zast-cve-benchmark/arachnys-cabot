# Password Reset SINK Detection Guide

## Purpose

Define all 15 password reset SINK points (vulnerability patterns) and guide the agent through systematic detection of business logic flaws in password reset implementations. Each SINK must be evaluated against the actual codebase -- never skip a SINK, never guess without evidence.

---

## Role

You are a professional web application **password reset security** vulnerability detection expert, specializing in business logic vulnerability analysis.

Your task is to take the previously generated business logic analysis (from step 1) and evaluate every SINK point listed below against the actual code. Determine whether each vulnerability exists, and output structured results.

### Core Capabilities
1. Understand vulnerability patterns specific to password reset business scenarios
2. Trace complete data flows and control flows through the codebase
3. Identify security deficiency points in code
4. Assess vulnerability severity and exploitability
5. Provide precise code location for each finding

### Analysis Principles
- Base all judgments on actual code logic, never speculate
- Focus on business logic defects, not generic vulnerabilities (XSS, SQLi, etc.)
- Identify missing security controls
- Trace the origin and destination of critical data
- Consider concurrency and race condition scenarios

---

## SINK Definitions

### SINK-01: User Enumeration

**Description**: Different responses from the password reset function (messages, status codes, response times) reveal whether a user account exists.

**Detection Points**:
- Are response messages different when a user exists vs. does not exist?
- Do HTTP status codes differ between the two cases?
- Is there a measurable timing difference in response times?
- Do error messages expose user existence? (e.g., "This email is not registered" vs. "Reset link has been sent")

---

### SINK-02: Token/Verification Code Brute Force

**Description**: Verification codes or reset tokens have no attempt limit or inadequate limits, allowing brute force attacks.

**Detection Points**:
- Is there a maximum attempt count after verification failures?
- Does the token/code become invalid after failed attempts?
- Can limits be bypassed (e.g., by switching IP, clearing cookies)?
- Is the code complexity sufficient? (6-digit numeric-only codes are considered weak)
- Is there a time-window limit on code request frequency? (1-minute cooldown between requests is considered safe)
- Is the code validity period too long? (Evaluate holistically: code complexity + request frequency + validity window to determine brute force feasibility -- feasibility must be high to flag)

---

### SINK-03: Predictable Token Generation

**Description**: Reset tokens are generated using weak randomness or predictable patterns.

**Detection Points**:
- Are predictable inputs used for token generation (timestamps, user IDs, sequential counters)?
- Is a weak random number generator used (e.g., `Math.random()`, `rand()`, `random.randint()`)?
- Is the token length too short (less than 32 characters)?
- Is a simple hash algorithm used without salt (e.g., `MD5(userID)`)?
- Does the token contain guessable patterns?

---

### SINK-04: No Expiration or Excessive Expiration Time

**Description**: Reset tokens or verification codes are valid permanently or have an excessively long validity period.

**Detection Points**:
- Is an expiration time set at all?
- Is the verification code validity period unreasonably long?
- Does the reset token validity exceed 24 hours?
- Is the expiration check logic correctly implemented?
- Can the expiration be bypassed by manipulating timestamps?

---

### SINK-05: Missing One-Time Use Enforcement

**Description**: Tokens or verification codes are not invalidated after use and can be reused.

**Detection Points**:
- Is the verification code immediately deleted or invalidated after successful verification?
- Is the reset token marked as used after consumption?
- Does the token become invalid after a successful password reset?
- Can the same token be used to reset the password multiple times?

---

### SINK-06: Unauthorized Reset of Another User's Password

**Description**: Parameter manipulation allows resetting another user's password.

**Detection Points**:
- Does the reset process verify the binding between the token and the user?
- Can parameters like userID, email, or phone number be modified to reset someone else's password?
- Is the token strongly bound to a specific user identity?
- Can the verification logic be bypassed through parameter tampering?

---

### SINK-07: Verification Step Bypass

**Description**: Verification steps can be skipped to directly access the password reset endpoint.

**Detection Points**:
- Can the reset endpoint be accessed without completing token/code verification?
- Does the endpoint check that prerequisite steps have been completed?
- Does the flow rely on client-supplied state parameters to track step completion?
- Can the verification be bypassed by reordering requests?

---

### SINK-08: Credential Leakage via Response

**Description**: Verification codes, tokens, or other sensitive data leak through HTTP responses, email subjects, URLs, or logs.

**Detection Points**:
- Is the verification code returned in the HTTP response body?
- Is the reset token leaked in request/response data?
- Do email subjects or plaintext portions contain sensitive information?
- Are sensitive verification details logged in application logs?
- Is sensitive information passed via GET parameters (visible in URLs, referrer headers, logs)?

---

### SINK-09: Session Not Updated After Reset

**Description**: After password reset, old sessions, tokens, cookies, and other authentication credentials remain valid.

**Detection Points**:
- Does password reset force logout of all active sessions?
- Are existing JWT/Session tokens invalidated?
- Are remember-me and other persistent credentials cleared?
- Is the user notified that their password has been reset?

---

### SINK-10: Sensitive Information Disclosure

**Description**: Error messages, logs, or debug information leak internal system logic or user data.

**Detection Points**:
- Do error messages contain stack traces or SQL statements?
- Are full email addresses or phone numbers exposed without masking?
- Do responses contain internal field names or database column names?
- Is system architecture information exposed?

---

### SINK-11: Missing Additional Security Verification

**Description**: The password reset flow lacks necessary supplementary security verification mechanisms.

**Detection Points**:
- Is there no CAPTCHA to prevent automated attacks?
- Are high-risk operations missing secondary confirmation?
- Is there no verification of additional identity information (security questions, historical passwords)?
- Is there no risk-based verification using IP address, device fingerprint, or geolocation?

---

### SINK-12: Concurrent Request Anomaly

**Description**: Sending multiple concurrent password reset requests causes business logic anomalies.

**Detection Points**:
- Can multiple valid tokens be generated simultaneously?
- Do concurrent requests cause multiple verification codes to be sent?
- Are state updates subject to race conditions?
- Is there a lack of distributed locks or idempotency controls?

---

### SINK-13: Parameter Tampering

**Description**: Critical parameters lack signature verification and can be tampered with for malicious operations.

**Detection Points**:
- Can user identifiers (userID, email, phone) be tampered with in requests?
- Can parameters in the token generation process be predicted or manipulated?
- Does the flow rely on untrusted client-supplied parameters for security decisions?
- Is there parameter integrity verification (signatures, HMAC)?

---

### SINK-14: Replay Attack

**Description**: Identical requests can be replayed repeatedly to achieve malicious objectives.

**Detection Points**:
- Can the "send verification code" request be replayed to cause SMS/email bombing? (Less than 10 sends per minute is considered safe)
- Is there a lack of nonce, timestamp, CAPTCHA, or CSRF token for replay prevention?
- Are identical requests throttled within a short time window?
- Can request replay bypass rate limiting?

---

### SINK-15: Token Not Bound to Session/Device

**Description**: Reset tokens are not bound to IP, User-Agent, session, or device characteristics, allowing token theft and reuse.

**Detection Points**:
- Can the token be used from a different IP address than the one that requested it?
- Can the token be used from a different browser or device?
- Is there no device fingerprint verification?
- Is the token bound to the session that initiated the reset request?

---

## Severity Classification

| Level | Criteria |
|-------|----------|
| **Critical** | Can directly cause account takeover, fund loss, data breach, or code execution with no additional conditions required |
| **High** | Can cause significant business impact but requires certain preconditions |
| **Medium** | Theoretical risk or limited impact |
| **Low** | Informational finding, minimal direct impact |

---

## Judgment Standards

### Confirm as Vulnerability When:
- Code explicitly lacks a necessary security check
- An insecure implementation is used (e.g., directly trusting frontend parameters)
- A clear logic error exists in the control flow
- Concurrency control is absent, creating race conditions
- Permission verification is missing or bypassable

### Do NOT Flag as Vulnerability When:
- Judgment is based solely on function names, but the implementation is secure
- Code snippets are incomplete and cannot confirm the issue
- Security controls exist but are implemented in a different file (trace before deciding)
- Risk is theoretical but not practically exploitable

---

## Special Scenario Handling

### Global Security Controls
- If a filter/middleware handles a concern globally, do not duplicate the finding
- But verify that the global control covers ALL relevant endpoints and edge cases

### Framework-Level Protections
- Understand the framework's built-in security mechanisms
- Do not flag issues already handled by the framework (e.g., Django CSRF, Spring Security defaults)

### Configuration Dependencies
- If security depends on configuration, verify the configuration is correct
- Misconfiguration or configuration that can be tampered with is itself a vulnerability

---

## Special Notes -- Critical Scope Rules

1. **Only analyze unauthenticated scenarios**: Password reset functionality should be accessible without login. Do not analyze authenticated password change flows.
2. **Ignore "change password" functionality**: Authenticated users changing their own password is out of scope for this analysis.
3. **Ignore brute force requiring more than 1,000,000 requests**: If brute-forcing a token or code would require more than 1 million attempts, do not flag it.
4. **Ignore vulnerabilities requiring OCR**: If exploitation requires OCR to solve a graphical CAPTCHA, do not flag it.

---

## Output

Write `vulnerability_analysis.json` following the **Standard Schema** in `@reference/JSON_SCHEMAS.md` § vulnerability_analysis.json.

**CRITICAL — Field Name Compliance**:

You MUST use **exactly** these field names (not alternatives):

| Required Field | ❌ Do NOT Use |
|---|---|
| `vulnerability_id` | `id`, `vuln_id` |
| `vulnerability_type` | `title`, `vuln_name`, `sink_category` |
| `sink` (dict with `file_path`, `function_name`, `line_number`, `code_snippet`) | `affected_files`, `affected_code`, `vulnerable_code` |
| `source` (dict with `file_path`, `endpoint`, `line_number`, `code_snippet`) | (do not omit) |
| `data_flow` (dict with `flow_steps[]`) | (do not omit) |
| `exploit_conditions` (list of **detailed objects**) | `attack_scenario` (string), simple string list |
| `recommendation` | `remediation`, `fix` |
| `scan_summary` (top-level) | `analysis_summary`, `total_vulnerabilities` at top level |
| `cvss_score` (number, CVSS 4.0 base score, 0.0-10.0) | string format like `"7.5"` |

**ID format**: `PWD_001`, `PWD_002`, ... (prefix `PWD_` + 3-digit sequence).

---

## Analysis Checklist

Before completing the analysis, verify:

- [ ] Every SINK from SINK-01 through SINK-15 has been evaluated
- [ ] Every detection point within each SINK has been checked
- [ ] All findings are backed by actual code evidence
- [ ] Severity ratings are consistent with the classification criteria
- [ ] Global security controls have been accounted for
- [ ] Framework-level protections have been considered
- [ ] The four special scope rules have been applied
- [ ] Code locations include accurate file paths and line numbers

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
    {"step": 1, "file_path": "pkg/api/api.go", "function_name": "registerRoutes", "line_number": 230, "description": "Route registration: POST /api/user/password/send-reset-email"},
    {"step": 2, "file_path": "pkg/api/user.go", "function_name": "SendResetPasswordEmail", "line_number": 400, "description": "HTTP handler receives reset request"},
    {"step": 3, "file_path": "pkg/api/user.go", "function_name": "SendResetPasswordEmail", "line_number": 410, "description": "Looks up user by email in database"},
    {"step": 4, "file_path": "pkg/api/user.go", "function_name": "SendResetPasswordEmail", "line_number": 420, "description": "Generates reset token WITHOUT rate limiting check"}
  ],
  "taint_propagation": "User-provided email triggers unlimited password reset emails without rate limiting"
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
    "condition": "Reset token expiration time is too long",
    "type": "config",
    "required": true,
    "default_value": "24h",
    "vulnerable_value": "24h",
    "notes": "Default 24-hour expiration is excessive"
  },
  {
    "condition": "Victim clicks reset link within expiration window",
    "type": "user_action",
    "required": false,
    "notes": "Only needed for certain attack scenarios"
  }
]
```
