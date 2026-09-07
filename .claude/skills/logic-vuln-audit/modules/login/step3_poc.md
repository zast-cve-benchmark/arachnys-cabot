# Login PoC Generation Guide

Module-specific guidance for the **Login Agent** during Step 3.
Read this alongside `@agents/BUSINESS_ANALYZER.md` (Step 3 section) and `@reference/POC_TEMPLATES.md` for the base class.

---

## Objective

Generate executable Python PoC scripts for each confirmed login vulnerability.
Each PoC must prove the vulnerability exists through a concrete, reproducible attack.

> All PoCs inherit from `BasePoC` (see POC_TEMPLATES.md).
> Language: Python 3 with `requests` library.
> Output: `{output_dir}/login/pocs/poc_{ID}.json` + `poc_{ID}.py`

---

## Login-Specific Exploitation Patterns

### Pattern 1: Authentication Bypass
```
Target SINKs: SINK-01, SINK-10 (2FA bypass)
Technique: Manipulate login request to skip credential verification
Examples:
  - Remove password field from request body
  - Send type-juggled values (PHP: password[]=, true, 0)
  - Access post-auth endpoints directly without completing login
  - Skip 2FA step by calling post-2FA resources directly
Verification: Receive a valid session/token without correct credentials
```

### Pattern 2: Credential Brute Force
```
Target SINKs: SINK-04, SINK-05, SINK-17
Technique: Automated password guessing when rate limiting is absent
Steps:
  1. Confirm CAPTCHA is absent or bypassable (SINK-05)
  2. Confirm no account lockout or rate limit (SINK-04, SINK-17)
  3. Send login requests in a loop with password wordlist
Verification: Successful login response with a guessed password
Note: Use a small wordlist (top 10 passwords) to prove the concept, not full brute force
```

### Pattern 3: Username Enumeration
```
Target SINKs: SINK-08
Technique: Differentiate valid vs. invalid usernames from server responses
Steps:
  1. Send login request with known-valid username + wrong password
  2. Send login request with known-invalid username + wrong password
  3. Compare: response body, status code, response time, headers
Verification: Observable difference that reveals username validity
```

### Pattern 4: JWT/Token Exploitation
```
Target SINKs: SINK-02, SINK-14
Technique: Forge, tamper, or replay authentication tokens
Examples:
  - Set JWT alg to "none" and remove signature
  - Decode JWT, modify claims (sub, role), re-sign with HS256 using public key
  - Replay an expired or revoked token
Verification: Server accepts the forged/tampered token
```

### Pattern 5: Session Fixation / Hijacking
```
Target SINKs: SINK-03
Technique: Force or steal a session ID to gain authenticated access
Steps:
  1. Obtain session ID before login (e.g., from Set-Cookie on login page)
  2. Authenticate with valid credentials
  3. Check if session ID changed after login
Verification: Pre-login session ID is still valid post-login (fixation confirmed)
```

### Pattern 6: OAuth/SSO Abuse
```
Target SINKs: SINK-11
Technique: Exploit flaws in OAuth/OIDC flow
Examples:
  - Tamper redirect_uri to redirect auth code to attacker domain
  - Replay authorization code
  - Omit or forge state parameter (CSRF on OAuth callback)
  - Exploit nOAuth: change email on IdP, authenticate as victim
Verification: Gain access to another user's account or steal authorization code
```

### Pattern 7: IP Restriction Bypass
```
Target SINKs: SINK-12
Technique: Spoof client IP to bypass IP-based restrictions
Steps:
  1. Send login request normally (expect block/rate-limit)
  2. Add X-Forwarded-For: 127.0.0.1 (or other trusted IP)
  3. Retry login request
Verification: Rate limit or IP block no longer applies
```

---

## PoC Code Requirements

1. **Inherit from BasePoC**: Use the class from `POC_TEMPLATES.md`
2. **Parameterized target**: `TARGET_URL`, `USERNAME`, `PASSWORD` as configurable constants at top
3. **Step-by-step execution**: Each attack step is a separate method with print output
4. **Success detection**: Clear programmatic check (status code, response body pattern, token validity)
5. **Error handling**: Catch network errors, timeouts, unexpected responses
6. **Minimal side effects**: Use read-only probes where possible; warn if the PoC may trigger lockout or state changes
7. **Comments**: Document what each step does and why, in `output_lang`

---

## Exploit Chain Awareness

Login vulnerabilities frequently combine into chains. Flag these combinations:

| Chain | SINKs Combined | Impact |
|-------|---------------|--------|
| Enumeration + Brute Force | SINK-08 + SINK-04 + SINK-05 | Full credential compromise |
| CAPTCHA Bypass + No Rate Limit | SINK-05 + SINK-04 | Automated password guessing |
| OAuth Redirect + Token Theft | SINK-11 + SINK-19 | Account takeover via stolen auth code |
| Session Fixation + Info Leak | SINK-03 + SINK-09 | Session hijacking with leaked data |
| IP Bypass + Brute Force | SINK-12 + SINK-04 | Bypass rate limiting, then brute force |

When generating PoCs for chained vulnerabilities, note the chain relationship in `poc_{ID}.json`
so the Chain & Reporter agent can compose full exploit chain PoCs in Phase 5.

---

## Output

For each vulnerability with severity >= High:
- `{output_dir}/login/pocs/poc_{ID}.json` -- structured exploit data
- `{output_dir}/login/pocs/poc_{ID}.py` -- executable Python script

For Medium/Low severity: generate PoC only if the vulnerability is confirmed exploitable.

Schema: see `@reference/JSON_SCHEMAS.md` section: poc_output.
