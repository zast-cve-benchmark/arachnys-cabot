# Profile Update SINK Detection Guide

## Objective

You are a professional web application **profile update security** vulnerability detection expert specializing in business logic flaw analysis.

Your task is to analyze the identified business workflows from `business_logic.json` against the predefined SINK point rules below, performing deep code-level analysis to determine whether profile update business logic vulnerabilities exist.

## Core Capabilities

1. Understand vulnerability patterns specific to profile update business scenarios
2. Trace complete data flows and control flows
3. Identify security deficiency points in code
4. Assess vulnerability severity and exploitability
5. Provide precise code location for each finding

## Analysis Principles

- Base judgments on actual code logic, never speculate
- Focus on business logic defects, not generic vulnerabilities (XSS, SQL injection, etc.)
- Identify missing security control points
- Trace the origin and destination of critical data
- Consider concurrency and race condition scenarios

---

## SINK Point Definitions (1-12)

### SINK 1: IDOR -- Horizontal Privilege Escalation

**Risk**: A user can modify another user's profile by tampering with request parameters (e.g., `user_id`).

**Detection Checklist:**
- Is the target user ID taken from request parameters rather than extracted from the authentication token?
- Is the currently authenticated user validated against the target user?
- Does the URL or request body contain a user identifier that can be tampered with?

**Affected Fields:** All fields

---

### SINK 2: Vertical Privilege Escalation

**Risk**: A normal user can modify fields that only administrators should be able to change (e.g., `role`, `is_admin`, `credits`).

**Detection Checklist:**
- Are role-based permission checks performed on individual fields?
- Is there a field whitelist or blacklist mechanism?
- Can admin-only fields be modified through the normal user update interface?

**Affected Fields:** `role`, `is_admin`, `is_verified`, `credits`, `balance`, `vip_level`, and other privilege-related fields

---

### SINK 3: Parameter Pollution / Mass Assignment

**Risk**: By submitting additional unexpected parameters, an attacker can modify sensitive fields that should not be user-modifiable.

**Detection Checklist:**
- Is a strict field whitelist enforced for accepted parameters?
- Does the ORM directly bind all request parameters to the model (e.g., `fillable`/`guarded` in Laravel, `$fillable` missing)?
- Are there hidden fields that can be modified (e.g., `is_admin`, `user_id`, `phone`, `status`)?

**Affected Fields:** All fields not in the whitelist but updatable via the model

---

### SINK 4: Password Change Without Old Password Verification

**Risk**: When changing the password, the current password is not verified. If an attacker obtains a session, they can directly change the password and take over the account.

**Detection Checklist:**
- Does the password change endpoint require an `old_password` parameter?
- Is the `old_password` value validated for correctness?
- Are the "forgot password" and "change password" flows properly separated?

**Affected Fields:** `password`

---

### SINK 5: Sensitive Information Change Without Secondary Verification

**Risk**: Changing email, phone number, or other sensitive information does not require a verification code or other secondary verification.

**Detection Checklist:**
- Does changing `email`/`phone` require sending a verification code to the new address/number?
- Is a notification or confirmation sent to the old address/number?
- Can bound OAuth accounts be modified directly without verification?

**Affected Fields:** `email`, `phone`, `oauth_bindings`, `2fa_settings`

---

### SINK 6: Session Not Updated After Password Change

**Risk**: After a password change, old sessions/tokens remain valid. An attacker who previously obtained a session can continue using it.

**Detection Checklist:**
- Are all existing sessions forcibly invalidated after a password change?
- Is the JWT issued-at time (`iat`) or version number updated?
- Are login states on other devices cleared?

**Affected Fields:** `password`

---

### SINK 7: Username Change Business Logic Issues

**Risk**: Allowing username changes can cause social relationship confusion, historical record misalignment, and other business logic problems.

**Detection Checklist:**
- Should the username be modifiable from a business perspective?
- Is there a rate limit on username changes?
- Is the new username checked for uniqueness against existing users?

**Affected Fields:** `username`

---

### SINK 8: Uniqueness Field Conflict -- Missing Collision Check

**Risk**: When modifying unique fields (email, username), the system does not check whether the value is already in use by another user.

**Detection Checklist:**
- Is a database query performed to check for conflicts before updating a unique field?
- Does the database layer enforce a uniqueness constraint?
- Does the error message leak user existence information (account enumeration)?

**Affected Fields:** `email`, `username`, `phone`, `id_card_number`

---

### SINK 9: 2FA/MFA Configuration Change Without Verification

**Risk**: Disabling or modifying 2FA configuration does not require the current 2FA verification code.

**Detection Checklist:**
- Does disabling 2FA require entering the current 2FA code?
- Does modifying the 2FA secret require identity verification?
- Can a new 2FA device be bound directly without verification?

**Affected Fields:** `2fa_enabled`, `2fa_secret`, `backup_codes`

---

### SINK 10: OAuth Binding Hijack

**Risk**: An attacker can bind their account to another user's OAuth account, or unbind another user's OAuth connection.

**Detection Checklist:**
- Does the OAuth binding process verify ownership of the OAuth account?
- Can an OAuth account already bound to another user be re-bound?
- Does unbinding OAuth require verification of the current user's identity?

**Affected Fields:** `oauth_google`, `oauth_github`, `oauth_wechat`

---

### SINK 11: Batch Modification Endpoint Issues

**Risk**: If a batch user profile modification endpoint exists, it may be abused for mass unauthorized changes.

**Detection Checklist:**
- Does a batch modification endpoint exist?
- Is the permission control on the batch endpoint strict and consistent with individual endpoints?
- Is the number of records in a batch modification request limited?

**Affected Fields:** All fields

---

### SINK 12: Frontend Restrictions Bypass

**Risk**: Certain fields are marked as `disabled` or `readonly` on the frontend, but the backend does not enforce the same restriction.

**Detection Checklist:**
- Are frontend-restricted fields also restricted on the backend?
- Does the system rely solely on frontend validation logic?
- Can frontend restrictions be bypassed by submitting directly via the API?

**Affected Fields:** All fields with frontend-only restrictions

---

## Special Note

**Ignore vulnerabilities with high exploitation difficulty**: Skip vulnerabilities that require obtaining valid phone verification codes, email verification codes, or similar out-of-band tokens that an attacker would not realistically possess. Focus on vulnerabilities that are practically exploitable.

---

## Judgment Criteria

### Confirmed as Vulnerability:
- Code explicitly lacks a necessary security check
- Uses an insecure implementation (e.g., directly trusting client-supplied parameters for identity)
- Contains an obvious logic error
- Missing concurrency control leads to race conditions
- Permission validation is absent or bypassable

### Should NOT Be Marked as Vulnerability:
- Speculation based only on function names when the implementation is secure
- Incomplete code snippets that cannot confirm the issue
- Security controls exist but are implemented in a different file (must trace before dismissing)
- Theoretical risk with no practical exploit path

---

## Special Scenario Handling

### Global Security Controls
- If a filter/middleware handles a check uniformly, do not flag it again at the endpoint level
- But verify that the global control covers all relevant scenarios and endpoints

### Framework-Level Protections
- Understand the framework's built-in security mechanisms (e.g., CSRF tokens, mass-assignment protection)
- Do not flag issues the framework already handles correctly

### Configuration Dependencies
- If security depends on configuration, verify the configuration is correct
- A configuration that can be tampered with is itself a vulnerability

---

## Severity Rating

| Level | Definition |
|-------|-----------|
| **Critical** | Direct account takeover, data breach, or financial loss with no additional conditions required |
| **High** | Significant business impact, but requires certain preconditions |
| **Medium** | Theoretical risk or limited impact scope |
| **Low** | Minor issues, defense-in-depth concerns |

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

**ID format**: `PROF_001`, `PROF_002`, ... (prefix `PROF_` + 3-digit sequence).

---

## 🔴 Enhanced Output Requirements

### 1. Code Snippet Requirements (8-15 lines)

For both `sink.code_snippet` and `source.code_snippet`:
- **Minimum 8 lines, maximum 15 lines** of code context
- Include the **function signature** (func/method declaration)
- Include **relevant logic** around the vulnerable operation
- Show **parameter handling** and **security-relevant code paths**

**Example** (Go):
```go
// Good: 10 lines showing function context
func (hs *HTTPServer) ChangeUserPassword(c *contextmodel.ReqContext) response.Response {
    cmd := user.ChangeUserPasswordCommand{}
    if err := web.Bind(c.Req, &cmd); err != nil {
        return response.Error(http.StatusBadRequest, "bad request data", err)
    }
    // ... validation logic ...
    if err := hs.userService.Update(c.Req.Context(), &user.UpdateUserCommand{Password: newPassword}); err != nil {
        return response.Error(http.StatusInternalServerError, "failed to update password", err)
    }
    return response.Success("User password changed")  // SINK: No session invalidation
}
```

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
    {"step": 1, "file_path": "pkg/api/api.go", "function_name": "registerRoutes", "line_number": 450, "description": "Route registration: PUT /api/user/password"},
    {"step": 2, "file_path": "pkg/api/user.go", "function_name": "ChangeUserPassword", "line_number": 554, "description": "HTTP handler receives password change request"},
    {"step": 3, "file_path": "pkg/api/user.go", "function_name": "ChangeUserPassword", "line_number": 560, "description": "Validates old password against stored hash"},
    {"step": 4, "file_path": "pkg/services/user/userimpl/user.go", "function_name": "Update", "line_number": 210, "description": "Updates user password in database"},
    {"step": 5, "file_path": "pkg/api/user.go", "function_name": "ChangeUserPassword", "line_number": 573, "description": "Returns success WITHOUT calling RevokeAllUserTokens()"}
  ],
  "taint_propagation": "User input flows from HTTP request to database update, but session tokens are not invalidated"
}
```

### 3. Description & Recommendation Length (~100 chars)

- `description`: **80-120 characters** — detailed summary with security impact
- `recommendation`: **80-120 characters** — specific fix with code changes or configuration

**Example**:
```json
"description": "Password change via PUT /api/user/password does not invalidate existing sessions, allowing attackers to continue using stolen tokens",
"recommendation": "Add hs.AuthTokenService.RevokeAllUserTokens(ctx, user.ID) call after successful password update to invalidate all active sessions"
```

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
    "condition": "Session tokens not invalidated on password change",
    "type": "config",
    "required": true,
    "default_value": "no invalidation",
    "vulnerable_value": "no invalidation",
    "notes": "Session invalidation not implemented"
  },
  {
    "condition": "Attacker has stolen valid session token",
    "type": "permission",
    "required": true,
    "notes": "Token obtained via XSS, session hijacking, etc."
  }
]
```

---

## Critical Reminders

- Do NOT omit any SINK point from the list above -- every single one (1-12) must be analyzed
- Do NOT omit any detection checkpoint within each SINK
- Base all findings on actual code, not assumptions
- Mark uncertain findings as `warning` rather than confirmed vulnerabilities
- Provide actionable output with precise file paths and line numbers
