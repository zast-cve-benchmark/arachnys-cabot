# Registration SINK Detection Guide

Module-specific SINK checklist for Step 2 of the Register Agent pipeline.
Use alongside `@agents/BUSINESS_ANALYZER.md` (the generic framework).

**Total SINKs**: 13 (SINK-01 through SINK-13). Do NOT skip any.

---

## SINK-01: Username / Email / Phone Enumeration

**Risk Level**: Medium
**Description**: Attackers determine whether a username, email, or phone number is already registered by observing differences in the registration response.

**Detection Checkpoints**:
- [ ] Response message differs for "already exists" vs. other errors (e.g., "Username taken" vs. generic "Registration failed")
- [ ] HTTP status code differs for duplicate vs. non-duplicate submissions
- [ ] Response timing differs measurably (timing side-channel) due to early-return on duplicate check
- [ ] Error field names in JSON response reveal which specific field is duplicated

**What to verify in code**:
- Compare the error response path for duplicate-found vs. validation-failure
- Check if uniqueness check queries hit different code paths with different latency
- Look for field-specific error messages vs. generic responses

---

## SINK-02: Duplicate / Batch Registration

**Risk Level**: High
**Description**: Missing or bypassable rate limiting allows attackers to create accounts in bulk.

**Detection Checkpoints**:
- [ ] IP-based rate limiting on registration endpoint (check middleware, config)
- [ ] Device fingerprint or session-based throttling
- [ ] Rate limit bypass vectors: X-Forwarded-For spoofing, cookie clearing, session rotation
- [ ] CAPTCHA as sole anti-automation measure (can be bypassed or outsourced)
- [ ] No server-side duplicate request detection (idempotency)

**What to verify in code**:
- Search for rate limiter middleware applied to registration route
- Check if rate limiter trusts client-supplied IP headers
- Verify CAPTCHA is enforced server-side and not just client-side

---

## SINK-03: CAPTCHA Bypass / Replay

**Risk Level**: High
**Description**: CAPTCHA mechanism is flawed, allowing bypass or reuse.

**Detection Checkpoints**:
- [ ] CAPTCHA value bound to session (session ID linked to CAPTCHA answer)
- [ ] CAPTCHA invalidated immediately after one use (single-use enforcement)
- [ ] Registration succeeds when CAPTCHA field is empty or missing
- [ ] Registration succeeds with any arbitrary CAPTCHA value
- [ ] Same CAPTCHA answer accepted on repeated submissions (replay)
- [ ] CAPTCHA has expiration / TTL
- [ ] Weak CAPTCHA solvable by simple OCR
- [ ] Hardcoded test/backdoor CAPTCHA values in code (e.g., `if captcha == "0000"`)
- [ ] CAPTCHA validation only in client-side JavaScript, not server-side
- [ ] CAPTCHA / verification code can target multiple recipients (phone, email)
- [ ] Image CAPTCHA dimensions controlled by client parameter (DoS vector)

**What to verify in code**:
- Trace CAPTCHA generation, storage, comparison, and deletion flow
- Check if CAPTCHA check can be skipped by omitting the parameter
- Search for hardcoded CAPTCHA values or debug/test bypasses

---

## SINK-04: Race Condition (TOCTOU)

**Risk Level**: High
**Description**: Time gap between uniqueness check (SELECT) and account creation (INSERT) allows concurrent requests to bypass uniqueness enforcement.

**Detection Checkpoints**:
- [ ] Uniqueness check (SELECT) and INSERT are NOT within a single atomic transaction
- [ ] Database table lacks a UNIQUE index/constraint on username/email/phone
- [ ] No database-level locking (SELECT FOR UPDATE, advisory lock) during check-then-insert
- [ ] Application relies solely on application-level check without DB constraint fallback
- [ ] Concurrent requests can both pass the check before either INSERT executes

**What to verify in code**:
- Check transaction boundaries around uniqueness-check + insert
- Inspect database migration / schema for UNIQUE constraints
- Look for optimistic vs. pessimistic locking patterns
- Test: can two simultaneous requests with the same username both succeed?

---

## SINK-05: Parameter Pollution / Mass Assignment

**Risk Level**: Critical
**Description**: Attackers inject extra parameters (role, is_admin, status, verified) that get bound to the user model, escalating privileges at registration.

**Detection Checkpoints**:
- [ ] Mass assignment / bulk binding used (e.g., `User(request.POST)`, `req.body`, `@RequestBody User`)
- [ ] Whitelist of allowed fields explicitly defined (e.g., `$fillable`, DTO with only safe fields)
- [ ] Sensitive fields (role, is_admin, status, email_verified, permissions) protected from user input
- [ ] Hidden fields in HTML form that map to privileged model attributes
- [ ] API accepts and persists fields not shown in documentation / UI

**What to verify in code**:
- Compare fields in the request DTO/form vs. fields in the database model
- Check if the model has `$guarded` / `$fillable` (PHP), `fields` / `exclude` (Python), readonly properties (Java DTO)
- Attempt adding `role=admin` or `is_admin=true` to registration payload in code path analysis

---

## SINK-06: Weak Password Policy

**Risk Level**: Medium
**Description**: Insufficient password complexity requirements make brute-force attacks feasible.

**Detection Checkpoints**:
- [ ] Minimum password length enforced (recommended >= 8)
- [ ] Character diversity required (uppercase, lowercase, digits, special chars)
- [ ] Common/breached password list checked (e.g., "password", "123456")
- [ ] Password policy enforced on server-side (not just client-side JavaScript)
- [ ] Maximum password length allows very short passwords (e.g., min=1)

**What to verify in code**:
- Find password validation logic (regex, validator class, library)
- Check if validation exists only in frontend code
- Search for password policy configuration values

---

## SINK-07: Email / Phone Verification Bypass

**Risk Level**: High
**Description**: Account can be used without verifying ownership of the claimed email or phone number.

**Detection Checkpoints**:
- [ ] Registration completes with account in "active" state without email/phone verification
- [ ] Login is allowed before verification step is completed
- [ ] Verification token/code is predictable (sequential, short numeric, timestamp-based)
- [ ] Verification status field can be tampered via parameter pollution (see SINK-05)
- [ ] Temporary/disposable email addresses not blocked (if relevant to business)

**What to verify in code**:
- Check account status after INSERT (active vs. pending)
- Check login handler: does it enforce `is_verified` / `email_verified` check?
- Inspect verification token generation for randomness and length

---

## SINK-08: Default Permissions / Role Misconfiguration

**Risk Level**: High
**Description**: Newly registered accounts receive excessive default permissions or roles.

**Detection Checkpoints**:
- [ ] Default role assigned during registration (inspect code: hardcoded vs. config)
- [ ] Default role has more permissions than necessary for a new user
- [ ] Role assignment is hardcoded in application code (not configurable)
- [ ] Configuration file containing default role is writable or injectable
- [ ] No principle of least privilege: new users can access admin or privileged functions

**What to verify in code**:
- Find where `role` / `permissions` / `user_type` is set during registration
- Check the permission set associated with the default role
- Verify if the default role value comes from a trusted source

---

## SINK-09: Sensitive Information Leakage

**Risk Level**: Medium
**Description**: Registration process exposes internal system details, credentials, or user data.

**Detection Checkpoints**:
- [ ] HTTP response body contains verification code / token
- [ ] Verification code embedded in HTML source or JavaScript variables
- [ ] Database error messages / stack traces returned to client on failure
- [ ] Internal file paths, class names, or query strings in error responses
- [ ] Registration response includes fields not needed by client (internal IDs, hashed passwords)
- [ ] Passwords or tokens written to application logs in plaintext

**What to verify in code**:
- Inspect error handling: are exceptions caught and sanitized?
- Check response serialization: which user fields are included?
- Search logs for password/token logging
- Check debug mode settings (e.g., `DEBUG=True`, `app.debug`)

---

## SINK-10: Account Activation / Approval Bypass

**Risk Level**: High
**Description**: Activation link or admin approval step can be skipped or forged.

**Detection Checkpoints**:
- [ ] Activation token is predictable (sequential ID, MD5 of email, short random)
- [ ] Account status can be changed directly via API (e.g., PUT /user with status=active)
- [ ] Admin approval flag stored client-side or in tamper-accessible location
- [ ] Activation step can be skipped by directly accessing post-activation endpoints
- [ ] Activation endpoint lacks authentication / rate limiting

**What to verify in code**:
- Inspect activation token generation: entropy, length, algorithm
- Check if any endpoint allows direct status update without authorization
- Trace the activation flow for mandatory sequence enforcement

---

## SINK-11: Session Fixation

**Risk Level**: Medium
**Description**: Session ID is not regenerated after successful registration, allowing session fixation attacks.

**Detection Checkpoints**:
- [ ] New session ID generated after registration completes (session regeneration)
- [ ] Pre-registration session ID carries over to authenticated session
- [ ] Framework session fixation protection enabled (e.g., Spring `sessionFixationProtection`, PHP `session_regenerate_id`)

**What to verify in code**:
- Check if `session.regenerate()` / `session_regenerate_id()` / equivalent is called after registration
- Check framework session configuration for fixation protection settings

---

## SINK-12: Email Bombing / SMS Bombing

**Risk Level**: Medium
**Description**: Registration verification flow can be abused to send unlimited messages to arbitrary email addresses or phone numbers.

**Detection Checkpoints**:
- [ ] Rate limiting on verification code sending endpoint (per target, per IP)
- [ ] Verification can be triggered for any email/phone without prior validation
- [ ] Same target can receive unlimited verification messages
- [ ] No cooldown period between resend requests
- [ ] Bulk targets possible in a single request (array of emails/phones)

**What to verify in code**:
- Find the "send verification code" endpoint
- Check for per-recipient rate limiting (not just global)
- Look for cooldown timers or send counters

---

## SINK-13: Logic Flow Skip

**Risk Level**: High
**Description**: Multi-step registration flow can be completed out of order, skipping required steps.

**Detection Checkpoints**:
- [ ] Multi-step registration enforces step completion order (state machine)
- [ ] Each step verifies that all prior steps are complete (server-side state check)
- [ ] Final registration step can be called directly without completing earlier steps
- [ ] Step state stored only client-side (hidden form fields, cookies, localStorage)
- [ ] No server-side session tracking of completed steps

**What to verify in code**:
- Identify all registration steps (if multi-step)
- Check if each step handler validates prior step completion
- Look for step tokens or server-side state tracking

---

## Analysis Protocol

For each SINK above:

1. **Locate** the relevant code using `business_logic.json` workflows
2. **Trace** the full data flow from source to sink
3. **Evaluate** whether adequate controls exist
4. **Classify**:
   - `fail` — vulnerability confirmed (control missing or flawed)
   - `pass` — control exists and is correctly implemented
   - `needs_review` — insufficient evidence to determine
5. **Document** with precise file path, line number, and code snippet

### Severity Guide (Registration Context)

| Severity | Registration Examples |
|----------|---------------------|
| Critical | Mass assignment to admin role (SINK-05), authentication bypass |
| High | Batch registration (SINK-02), CAPTCHA bypass (SINK-03), race condition (SINK-04), verification bypass (SINK-07), activation bypass (SINK-10), flow skip (SINK-13) |
| Medium | User enumeration (SINK-01), weak password (SINK-06), info leakage (SINK-09), session fixation (SINK-11), email bombing (SINK-12) |
| Low | Best-practice violations with minimal practical impact |

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

**ID format**: `REG_001`, `REG_002`, ... (prefix `REG_` + 3-digit sequence).

Every SINK (01-13) MUST appear in the output, even if the result is `pass`.

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
    {"step": 1, "file_path": "pkg/api/api.go", "function_name": "registerRoutes", "line_number": 220, "description": "Route registration: POST /api/user/signup"},
    {"step": 2, "file_path": "pkg/api/signup.go", "function_name": "SignUp", "line_number": 29, "description": "HTTP handler receives signup request"},
    {"step": 3, "file_path": "pkg/api/signup.go", "function_name": "SignUp", "line_number": 40, "description": "Queries database for existing user by email"},
    {"step": 4, "file_path": "pkg/api/signup.go", "function_name": "SignUp", "line_number": 47, "description": "Returns 422 error revealing user existence"}
  ],
  "taint_propagation": "User-provided email flows to database query, error response leaks existence information"
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

**Condition Types**:
| Type | Description | Requires default_value? |
|------|-------------|-------------------------|
| `config` | Configuration setting | ✅ Yes (MUST include default_value and vulnerable_value) |
| `permission` | User role or access level | ❌ No |
| `network` | Network accessibility | ❌ No |
| `environment` | Deployment/infrastructure | ⚠️ If applicable |
| `user_action` | Victim interaction required | ❌ No |
| `timing` | Time-sensitive condition | ❌ No |

**Example**:
```json
"exploit_conditions": [
  {
    "condition": "Email verification is disabled",
    "type": "config",
    "required": true,
    "default_value": "false",
    "vulnerable_value": "false",
    "notes": "Email verification disabled by default"
  },
  {
    "condition": "Network access to registration endpoint",
    "type": "network",
    "required": true,
    "notes": "Direct HTTP/HTTPS access required"
  }
]
```
