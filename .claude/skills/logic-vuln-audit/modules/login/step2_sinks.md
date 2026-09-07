# Login / Authentication SINK Detection Guide

Complete SINK checklist for the **Login Agent** during Step 2.
Each SINK defines a specific vulnerability pattern to check against the codebase.

**Input**: `login/business_logic.json` from Step 1.
**Output**: `login/vulnerability_analysis.json` — see `@reference/JSON_SCHEMAS.md`.

---

## Scope Reminder (范围说明)

> **This module covers ALL authentication mechanisms**, including but not limited to:
> - Traditional login forms with username/password
> - JWT token validation and lifecycle
> - Bearer token / API key authentication
> - OAuth 2.0 / OIDC / SSO flows
> - Session-based authentication
> - Config-file-based user authentication (e.g., vmauth)
> - Proxy authentication / API gateway auth
>
> Apply ALL SINKs below to whatever authentication mechanism exists in the codebase.
> For example, if the project has no login form but uses JWT auth, focus on JWT-related SINKs.

---

## How to Use This Checklist

For **every** SINK below:
1. Locate the relevant code using the workflows from `business_logic.json`
2. Trace the full data flow: Source -> Processing -> SINK point
3. Check whether adequate security controls exist
4. If controls are missing or flawed -> record as a vulnerability finding
5. If controls exist and are correct -> skip (no finding)
6. If uncertain -> mark as `needs_review`

> CRITICAL: Do NOT skip any SINK. Review this list three times.
> You MUST check every single SINK, even if you believe it is unlikely.
>
> 关键: 不可遗漏任何一个 SINK 点。每个都必须检查，逐一确认。

---

## SINK-01: Authentication Bypass (认证绕过)

**Description**: Credential verification logic can be circumvented, allowing login without valid credentials.

**Detection Checkpoints**:
- Is the password comparison using a constant-time function? (prevent timing attacks)
- Can the authentication check be skipped via parameter manipulation? (e.g., removing password field, sending empty string, null, or special values)
- Are there alternative authentication paths that bypass the main credential check? (debug endpoints, backdoor routes, legacy login handlers)
- Does the auth logic use short-circuit evaluation that can be exploited? (e.g., `if (isAdmin || checkPassword())`)
- Is the login function reachable without going through required middleware?
- Can authentication be bypassed via type juggling? (PHP `==` vs `===`, JavaScript loose equality)

**Risk Level**: Critical

---

## SINK-02: JWT Security Flaws (JWT 安全缺陷)

**Description**: JWT token generation, validation, or lifecycle management contains exploitable weaknesses.

**Detection Checkpoints**:
- **Algorithm confusion**: Does the server accept `alg: none`? Can RS256 be downgraded to HS256?
- **Signature verification**: Is signature actually verified on every request? Is the verification library used correctly?
- **Secret strength**: Is the JWT signing secret hardcoded? Is it a weak/guessable value? (e.g., `secret`, `123456`, `changeme`)
- **Claims validation**: Are `exp`, `iss`, `aud` claims checked? Is `exp` enforced correctly?
- **Token storage**: Is the token stored securely client-side? (HttpOnly cookie vs localStorage)
- **Token refresh**: Is the refresh token flow secure? Can refresh tokens be reused after rotation?
- **Key management**: Where is the signing key stored? Is it in source code, config file, or vault?
- **Token revocation**: Is there a mechanism to invalidate tokens before expiry? (blacklist, version counter)

**Risk Level**: Critical (algorithm confusion, missing verification) / High (weak secret, missing claims)

---

## SINK-03: Session Management Flaws (会话管理缺陷)

**Description**: Session lifecycle management has weaknesses that enable session hijacking or fixation.

**Detection Checkpoints**:
- **Session fixation**: Is the session ID regenerated after successful login? Compare pre-login and post-login session identifiers
- **Session ID quality**: Is the session ID generated using a cryptographically secure random generator? Sufficient entropy? (>= 128 bits)
- **Session expiration**: Is there an absolute timeout? Is there an idle timeout? Are values reasonable?
- **Session invalidation on logout**: Is the session actually destroyed server-side on logout? Or only client-side cookie deleted?
- **Concurrent sessions**: Is there a limit on concurrent sessions per user? Can an attacker maintain persistence?
- **Cookie attributes**: Are `HttpOnly`, `Secure`, `SameSite`, `Path`, `Domain` properly set?
- **Session storage**: Where are sessions stored? (memory, database, Redis) Is the storage access controlled?

**Risk Level**: High

---

## SINK-04: Brute Force / Rate Limiting (暴力破解 / 频率限制)

**Description**: Login endpoint lacks adequate protection against automated credential guessing attacks.

**Detection Checkpoints**:
- **Login attempt limiting**: Is there a maximum number of failed attempts before lockout/delay?
- **Lockout scope**: Is limiting per-account, per-IP, or both? (per-IP only is insufficient; per-account only enables DoS)
- **Lockout duration**: How long does lockout last? Is it progressive? (e.g., 1min, 5min, 30min)
- **Lockout bypass**: Can the lockout be reset by a successful login from elsewhere? Can it be bypassed by changing IP (without per-account limit)?
- **Response timing**: Do successful and failed logins have similar response times? (prevent timing-based enumeration)
- **Distributed attack**: Does rate limiting work across distributed IPs? (e.g., using IP rotation)
- **API vs. web**: Are both the web login form and the API login endpoint rate-limited?
- **Account lockout DoS**: Can an attacker lock out legitimate users? Is there a recovery mechanism?

**Risk Level**: High

---

## SINK-05: CAPTCHA Weaknesses (验证码缺陷)

**Description**: CAPTCHA mechanism can be bypassed or is missing, enabling automated attacks.

**Detection Checkpoints**:
- **CAPTCHA presence**: Is CAPTCHA implemented at all on the login form?
- **Server-side validation**: Is CAPTCHA validated on the server, or only client-side JavaScript?
- **Single-use enforcement**: Is each CAPTCHA token invalidated after one use? Can a solved CAPTCHA be replayed?
- **CAPTCHA-login binding**: Is the CAPTCHA answer bound to the specific login request? (prevent token reuse across sessions)
- **Generation predictability**: Are CAPTCHA answers derived from predictable factors? (sequential numbers, timestamp-based, weak random)
- **Bypass via omission**: Can the login succeed if the CAPTCHA parameter is simply removed from the request?
- **Rate limiting interaction**: If CAPTCHA is bypassed, does brute-force protection still apply independently?
- **Third-party CAPTCHA**: If using reCAPTCHA/hCaptcha, is the server-side secret key verification implemented? Is the response token validated?

**Risk Level**: Medium (missing CAPTCHA alone) / High (if combined with no rate limiting = brute force possible)

---

## SINK-06: Password Storage Security (密码存储安全)

**Description**: Password hashing, salting, or storage implementation has weaknesses.

**Detection Checkpoints**:
- **Hashing algorithm**: Is a modern algorithm used? (bcrypt, argon2, scrypt = GOOD; md5, sha1, sha256 without iterations = BAD)
- **Salt usage**: Is each password individually salted? Is the salt random and of sufficient length?
- **Salt storage**: Is the salt stored separately or as part of the hash? (both are acceptable with proper algorithms)
- **Iteration count**: For PBKDF2/bcrypt, is the work factor adequate? (bcrypt cost >= 10, PBKDF2 iterations >= 100000)
- **Plaintext storage**: Are passwords stored in plaintext anywhere? (database, logs, config files, debug output)
- **Password in memory**: Are passwords cleared from memory after use? (defense-in-depth)
- **Password transmission**: Is the password sent over HTTPS? Is it encrypted client-side before transmission?

**Risk Level**: High (weak algorithm) / Critical (plaintext storage)

---

## SINK-07: Hardcoded Credentials (硬编码凭证)

**Description**: Credentials, tokens, or secrets are hardcoded in source code.

**Detection Checkpoints**:
- **Backend hardcoded passwords**: Are there hardcoded username/password pairs in backend code? (admin accounts, test accounts, service accounts)
- **Frontend hardcoded credentials**: Are credentials visible in JavaScript, HTML, or client-side configuration?
- **Default credentials**: Does the application ship with default admin/admin, root/root, or similar credentials?
- **Hardcoded API keys/tokens**: Are API keys, JWT secrets, or OAuth client secrets hardcoded in source?
- **Configuration file secrets**: Are credentials in config files that are committed to version control? (.env committed, application.yml with plaintext secrets)
- **Debug/test backdoors**: Are there debug login routes or test account bypasses left in production code?
- **Comments containing secrets**: Are passwords or keys left in code comments?

**Risk Level**: Critical (admin backdoor) / High (default credentials, hardcoded secrets)

---

## SINK-08: Information Leakage via Error Messages (错误信息泄露)

**Description**: Login error responses reveal whether a username exists or provide other exploitable information.

**Detection Checkpoints**:
- **Username enumeration**: Does the error message distinguish between "user not found" and "wrong password"? (They should be identical, e.g., "Invalid credentials")
- **Account status leakage**: Do error messages reveal account states? (e.g., "Account is locked", "Account is disabled", "Account not verified" — these confirm the account exists)
- **Timing-based enumeration**: Is there a measurable time difference between "user exists + wrong password" vs. "user does not exist"? (database lookup timing)
- **Stack trace exposure**: Are detailed error messages or stack traces returned on login failure?
- **HTTP status code differences**: Do different failure reasons return different HTTP status codes?
- **Response body differences**: Do different failure reasons return different response body structures or field counts?
- **Password policy leakage**: Does the login form reveal password requirements that help narrow brute-force scope?

**Risk Level**: Medium

---

## SINK-09: Credential Exposure in Response (响应中泄露凭证)

**Description**: Sensitive authentication data is included in HTTP responses.

**Detection Checkpoints**:
- **Password in response**: Is the password (even hashed) returned in the login success response?
- **Token in URL**: Is the session ID or JWT token passed via GET query parameter instead of cookie/header? (leaks via Referer, logs, browser history)
- **Verbose user object**: Does the login response include sensitive fields? (password hash, security questions, internal user ID, role details)
- **Response headers**: Are sensitive tokens leaked via custom response headers that shouldn't be there?
- **Redirect URL leakage**: After login, does the redirect URL contain the token as a query parameter?
- **Debug information**: Does the response include debug data containing credentials or internal state?

**Risk Level**: High (password in response) / Medium (excessive user data)

---

## SINK-10: 2FA/MFA/OTP Bypass (双因素认证绕过)

**Description**: Multi-factor authentication implementation can be circumvented.

**Detection Checkpoints**:
- **Step bypass**: Can the 2FA verification step be skipped by directly accessing post-login resources? (missing server-side state check for 2FA completion)
- **OTP reuse**: Can the same OTP code be used multiple times within its validity window?
- **OTP brute force**: Is there a limit on OTP verification attempts? (6-digit OTP = 1 million possibilities)
- **OTP generation weakness**: Is the OTP generated using a predictable algorithm? (sequential, time-based with insufficient entropy)
- **Backup code abuse**: Are backup codes single-use? Are they rate-limited? Can they be enumerated?
- **2FA enrollment bypass**: Can an attacker disable or reset 2FA for a target account without full authentication?
- **Remember device bypass**: Is the "trusted device" token secure? Can it be forged or transferred to another device?
- **Race condition**: Can two parallel requests with the same OTP both succeed?

**Risk Level**: Critical (step bypass) / High (brute force, reuse)

---

## SINK-11: SSO/OAuth/OIDC Implementation Flaws (SSO/OAuth/OIDC 实现缺陷)

**Description**: Single Sign-On or OAuth/OIDC integration contains exploitable logic flaws.

**Detection Checkpoints**:
- **State parameter**: Is the `state` parameter used in OAuth flow? Is it validated on callback? (CSRF protection)
- **Redirect URI validation**: Is the `redirect_uri` strictly validated? Can it be manipulated to redirect tokens to attacker-controlled domains? (open redirect, path traversal, subdomain matching)
- **Authorization code replay**: Can the authorization code be reused? Is it single-use and time-bound?
- **nOAuth vulnerability**: When identifying users from the IdP, is the immutable `sub` claim used? Or are mutable fields like `email`, `preferred_username` used? (email change = account takeover)
- **PKCE for public clients**: For public clients (SPA, mobile), is PKCE (Proof Key for Code Exchange) implemented?
- **Token validation**:
  - Is the token signature verified?
  - Are the accepted signing algorithms restricted? (prevent algorithm confusion)
  - Is the `iss` (issuer) claim validated against the expected IdP?
  - Is `exp` (expiration) enforced?
  - Is `aud` (audience) verified to match this application's client ID?
- **Account linking**: When an external identity (Google, GitHub) maps to a local account, is the linking deterministic? Is a new account silently created without user confirmation for unrecognized external identities?
- **Callback endpoint protection**: Is the OAuth callback endpoint protected against CSRF? Can it be called directly with forged parameters?

**Risk Level**: Critical (nOAuth, redirect URI bypass, missing state) / High (token validation gaps, account linking flaws)

---

## SINK-12: IP-Based Restriction Bypass (IP 限制绕过)

**Description**: IP-based access controls or rate limiting can be bypassed via header manipulation.

**Detection Checkpoints**:
- **Client IP source**: How does the application determine the client's IP? Does it trust proxy headers?
- **Spoofable headers**: Does the code read IP from `X-Forwarded-For`, `X-Real-IP`, `X-Client-IP`, `CF-Connecting-IP`, `True-Client-IP`, or similar headers that clients can forge?
- **Header priority**: If multiple IP headers exist, which takes precedence? Can an attacker prepend a fake IP?
- **IP parsing**: Is only the first IP in `X-Forwarded-For` used? Or the last? (should use the rightmost trusted proxy's value)
- **Whitelist bypass**: If certain IPs bypass authentication (internal networks), can an attacker spoof those IPs?
- **IPv4/IPv6 inconsistency**: Are restrictions applied consistently across IPv4 and IPv6? Can switching protocol bypass limits?
- **Rate limit reset**: Does changing the spoofed IP header reset rate-limiting counters?

**Risk Level**: High (if IP is used for auth bypass) / Medium (if only used for rate limiting)

---

## SINK-13: Login Credential in GET Request (GET 请求中的登录凭证)

**Description**: Sensitive credentials are transmitted via URL query parameters.

**Detection Checkpoints**:
- **Login form method**: Does the login form use GET instead of POST?
- **Token in URL**: Is the session token or JWT passed as a URL parameter? (e.g., `?token=xxx`, `?sid=xxx`)
- **Redirect with credentials**: After login, does a redirect include credentials in the URL?
- **API token in query**: Are API authentication tokens passed as query parameters instead of headers?
- **Leakage vectors**: GET parameters appear in browser history, server access logs, Referer headers, proxy logs, and browser bookmarks

**Risk Level**: Medium

---

## SINK-14: Session Token Lifecycle (会话令牌生命周期)

**Description**: Token/session lifecycle management has gaps enabling persistence or replay attacks.

**Detection Checkpoints**:
- **Token uniqueness**: Is each login generating a unique token? Can the same token be predicted or duplicated?
- **Cryptographic randomness**: Is the token generated using `SecureRandom` (Java), `random_bytes` (PHP), `secrets` (Python), `crypto/rand` (Go), `crypto.randomBytes` (Node)?
- **Expiration enforcement**: Is the expiration actually checked on every request, not just at issuance?
- **Logout invalidation**: On logout, is the token/session invalidated server-side? Or is it only deleted client-side?
- **Token rotation**: Are long-lived sessions periodically rotated to limit the window of token theft?
- **Concurrent invalidation**: When a user changes their password, are all existing sessions invalidated?
- **Token scope**: Is the token scoped to the correct user, role, and permissions? Can a token from one user be used for another?

**Risk Level**: High

---

## SINK-15: Password Security Policy (密码安全策略)

**Description**: Password policy is weak or not enforced, enabling use of easily guessable passwords.

**Detection Checkpoints**:
- **Minimum length**: Is there a minimum password length? (Should be >= 8, recommended >= 12)
- **Complexity rules**: Are there requirements for uppercase, lowercase, digits, special characters?
- **Common password check**: Does the system reject passwords from common password lists? (e.g., `password`, `123456`, `qwerty`)
- **Server-side enforcement**: Is the policy enforced server-side, or only via client-side JavaScript?
- **Policy consistency**: Is the same policy applied at registration, password change, and password reset?
- **Maximum length**: Is there a reasonable maximum? (prevent DoS via very long passwords, but should be >= 64)

**Risk Level**: Medium

---

## SINK-16: Remember Me / Persistent Login (记住登录 / 持久化登录)

**Description**: "Remember me" functionality creates a long-lived token with insufficient security.

**Detection Checkpoints**:
- **Token security**: Is the remember-me token cryptographically random? Or derived from predictable data? (e.g., base64(username:timestamp))
- **Token storage**: Is the token stored securely server-side? (database with hashed value vs. plaintext)
- **Token scope**: Can the remember-me token be used for sensitive operations? (should require re-authentication for password change, payment, etc.)
- **Token expiration**: Is there a maximum lifetime for remember-me tokens?
- **Token invalidation**: Is the remember-me token invalidated on password change? On explicit logout?
- **Cookie security**: Does the remember-me cookie have `HttpOnly`, `Secure`, and `SameSite` attributes?

**Risk Level**: Medium / High (if token is predictable or never expires)

---

## SINK-17: Account Lockout Implementation (账户锁定实现)

**Description**: Account lockout mechanism is missing, flawed, or can be weaponized for denial of service.

**Detection Checkpoints**:
- **Lockout existence**: Is there any account lockout after failed attempts?
- **Lockout threshold**: What is the threshold? (Should be 3-10 failed attempts)
- **Lockout duration**: Is it time-based or permanent? (Permanent lockout = DoS vector)
- **Counter persistence**: Is the failure counter stored reliably? (In-memory counter resets on server restart)
- **Counter reset on success**: Does a successful login reset the counter?
- **Lockout notification**: Is the user/admin notified of lockout events?
- **Lockout bypass**: Can the lockout be bypassed by using a different login endpoint (API vs. web) or by manipulating request parameters?
- **DoS prevention**: Can an attacker lock out any user account? Is there a CAPTCHA before lockout to slow automated attacks?

**Risk Level**: Medium (missing lockout) / High (if combined with no CAPTCHA = brute force chain)

---

## SINK-18: Race Condition in Login Flow (登录流程竞态条件)

**Description**: Concurrent login requests can exploit race conditions in authentication or session management.

**Detection Checkpoints**:
- **Concurrent login requests**: Can multiple simultaneous login requests bypass attempt counters? (TOCTOU on failure count)
- **Session creation race**: Can parallel successful logins create inconsistent session state?
- **Token issuance race**: Can two concurrent requests both receive valid tokens when only one should?
- **OTP verification race**: Can the same OTP be consumed by two parallel requests?
- **Lockout counter race**: Can rapid parallel requests exceed the lockout threshold without triggering the lock?
- **Database transaction isolation**: Is the login logic wrapped in a transaction with appropriate isolation level?

**Risk Level**: Medium / High (if bypasses critical security controls)

---

## SINK-19: Login Redirect / Open Redirect (登录重定向 / 开放重定向)

**Description**: Post-login redirect mechanism can be abused to redirect users to malicious sites.

**Detection Checkpoints**:
- **Redirect parameter**: Is there a `redirect_url`, `next`, `return_to`, or `goto` parameter?
- **Validation**: Is the redirect target validated against a whitelist? Or only checked for same-domain?
- **Bypass techniques**: Can validation be bypassed using: `//evil.com`, `\/\/evil.com`, `https://evil.com@legitimate.com`, URL encoding, or null bytes?
- **Protocol validation**: Does validation prevent `javascript:` or `data:` protocol URLs?
- **Token leakage**: If a token is appended to the redirect URL, an open redirect leaks the token to the attacker's domain

**Risk Level**: Medium (open redirect alone) / High (if combined with token leakage)

---

## SINK-20: Insecure Authentication Protocol/Transport (不安全的认证协议/传输)

**Description**: Credentials are transmitted or processed over insecure channels.

**Detection Checkpoints**:
- **HTTPS enforcement**: Is HTTPS required for the login endpoint? Is HTTP-to-HTTPS redirect in place?
- **HSTS header**: Is `Strict-Transport-Security` configured to prevent SSL stripping?
- **Mixed content**: Does the login page load any resources over HTTP? (script injection vector)
- **Certificate validation**: In server-to-server auth flows, is TLS certificate verification enabled? (no `verify=False`, no `InsecureSkipVerify`)
- **Credential logging**: Are credentials logged in access logs, application logs, or error logs?

**Risk Level**: High (plaintext transmission) / Medium (logging, mixed content)

---

## Analysis Requirements Reminder

### Depth Standards
- Do NOT do shallow pattern matching -- understand the actual implementation
- Track data flow end-to-end: user input -> parameter binding -> business logic -> database -> response
- Consider edge cases: empty input, null values, type coercion, encoding tricks
- Check all login paths: primary login, API login, mobile login, OAuth callback, SSO

### Judgment Criteria

**IS a vulnerability**:
- Security control is missing where it should exist
- Security control exists but has a logic flaw enabling bypass
- Implementation uses insecure patterns (weak crypto, predictable tokens, plaintext secrets)

**Is NOT a vulnerability**:
- Control exists in a different file/layer but is correctly applied
- Framework provides built-in protection and it is properly enabled
- Theoretical risk with no practical exploitation path

### Severity Reference

| Severity | Login-Specific Examples |
|----------|----------------------|
| Critical | Auth bypass, JWT alg:none accepted, admin backdoor, nOAuth account takeover |
| High | Missing rate limiting + no CAPTCHA, session fixation, weak JWT secret, credential in response |
| Medium | Username enumeration, missing lockout, open redirect, weak password policy |
| Low | Best practice violations with minimal exploitability |

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

**ID format**: `LOGIN_001`, `LOGIN_002`, ... (prefix `LOGIN_` + 3-digit sequence).

Ensure every SINK (01-20) has been explicitly evaluated -- either as a finding or as "checked, not vulnerable."

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
    {"step": 1, "file_path": "pkg/api/api.go", "function_name": "registerRoutes", "line_number": 300, "description": "Route registration: POST /login"},
    {"step": 2, "file_path": "pkg/api/login.go", "function_name": "LoginPost", "line_number": 50, "description": "HTTP handler receives login request"},
    {"step": 3, "file_path": "pkg/api/login.go", "function_name": "LoginPost", "line_number": 75, "description": "Checks if rate limiting is enabled (default: disabled)"},
    {"step": 4, "file_path": "pkg/api/login.go", "function_name": "LoginPost", "line_number": 90, "description": "Authenticates user without IP-based protection"}
  ],
  "taint_propagation": "Login request bypasses rate limiting due to disabled IP protection"
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
    "condition": "skip_verify config option is enabled",
    "type": "config",
    "required": true,
    "default_value": "false",
    "vulnerable_value": "true",
    "notes": "Must be explicitly enabled in vmauth config"
  },
  {
    "condition": "Network access to vmauth endpoint",
    "type": "network",
    "required": true,
    "notes": "Direct HTTP/HTTPS access required"
  },
  {
    "condition": "Attacker knows JWT claim structure",
    "type": "permission",
    "required": false,
    "notes": "Increases exploit reliability; can be discovered via error messages"
  }
]
```

**Why Detailed Conditions Matter**:
- Helps security teams assess real-world exploitability
- Identifies default-insecure configurations vs. misconfiguration-dependent vulnerabilities
- Enables accurate risk prioritization (exploitable by default = higher priority)
