# Registration PoC Generation Guide

Module-specific PoC guidance for Step 3 of the Register Agent pipeline.
Use alongside `@agents/BUSINESS_ANALYZER.md` and `@reference/POC_TEMPLATES.md`.

---

## Scope

Generate executable Python PoC scripts for each confirmed registration vulnerability.
Read `vulnerability_analysis.json` from Step 2 for the list of findings.

---

## Registration-Specific Exploitation Patterns

### Batch Registration (SINK-02, SINK-03)

Exploit missing rate limits or CAPTCHA enforcement to create accounts in bulk.

```
Pattern:
  1. Observe registration endpoint (method, URL, required fields)
  2. Loop N iterations with unique usernames (generated or sequential)
  3. For each iteration: POST registration request, record success/failure
  4. Report: accounts created vs. blocked, rate limit trigger point
```

PoC considerations:
- Generate unique usernames/emails per iteration (e.g., `testuser_{i}@example.com`)
- Track response codes and messages to detect when rate limiting kicks in
- Include configurable delay between requests for stealth mode
- Add cleanup note: list created accounts for manual removal

### Race Condition (SINK-04)

Exploit TOCTOU gap with concurrent requests.

```
Pattern:
  1. Prepare N identical registration payloads (same username/email)
  2. Launch all requests concurrently (threading or asyncio)
  3. Collect all responses
  4. Check: how many returned success? >1 means race condition confirmed
  5. Verify in DB: count records with the target username
```

PoC considerations:
- Use `concurrent.futures.ThreadPoolExecutor` for parallel HTTP requests
- Typical thread count: 5-20 concurrent requests
- All threads must fire as close to simultaneously as possible
- Success = more than one 200/201 response for the same unique identifier

### Parameter Tampering / Mass Assignment (SINK-05)

Inject extra fields to escalate privileges.

```
Pattern:
  1. Send normal registration request, record created account's role/status
  2. Send registration request with injected fields (role=admin, is_admin=1, status=active)
  3. Compare: does injected account have elevated role/status?
  4. Verify by logging in and accessing admin-only endpoints
```

PoC considerations:
- Test multiple field names: `role`, `is_admin`, `user_type`, `permissions`, `group`, `level`
- Try both JSON body and form-encoded body
- Include a verification step: login with new account, call a restricted endpoint

### User Enumeration (SINK-01)

Detect information leakage through differential responses.

```
Pattern:
  1. Register with a known-existing username/email -> capture response
  2. Register with a definitely-nonexistent username/email -> capture response
  3. Compare: response body, status code, response time
  4. Differences confirm enumeration is possible
```

### Verification / Activation Bypass (SINK-07, SINK-10)

Skip or forge the verification step.

```
Pattern:
  1. Register a new account (status should be "pending" or "unverified")
  2. Attempt login without completing verification -> record result
  3. Attempt direct access to authenticated endpoints -> record result
  4. If activation token is predictable: generate candidate tokens, call activation endpoint
```

### Email/SMS Bombing (SINK-12)

Abuse verification code resend to flood a target.

```
Pattern:
  1. Trigger initial registration or verification code request
  2. Repeatedly call the resend/send-verification endpoint for same target
  3. Count successful sends before rate limit triggers (or lack thereof)
```

---

## PoC Structure

All PoCs MUST inherit from `BasePoC` (see `@reference/POC_TEMPLATES.md`).

Each PoC file (`poc_{ID}.py`) must:
- Accept `--target` (base URL) as a command-line argument
- Have configurable parameters at the top (usernames, passwords, thread count)
- Print step-by-step execution output with clear success/failure indicators
- Return exit code 0 on confirmed vulnerability, 1 on not confirmed
- Include comments in the language specified by `output_lang` in `_session.json`

---

## PoC Priority

| SINK | Severity | PoC Required |
|------|----------|-------------|
| SINK-05 (mass assignment) | Critical | MUST |
| SINK-02 (batch reg) | High | MUST |
| SINK-03 (CAPTCHA bypass) | High | MUST |
| SINK-04 (race condition) | High | MUST |
| SINK-07 (verification bypass) | High | MUST |
| SINK-08 (default perms) | High | MUST |
| SINK-10 (activation bypass) | High | MUST |
| SINK-13 (flow skip) | High | MUST |
| SINK-01 (enumeration) | Medium | RECOMMENDED |
| SINK-06 (weak password) | Medium | RECOMMENDED |
| SINK-09 (info leakage) | Medium | RECOMMENDED |
| SINK-11 (session fixation) | Medium | RECOMMENDED |
| SINK-12 (email bombing) | Medium | RECOMMENDED |

Only generate PoCs for vulnerabilities that were confirmed (`fail`) in Step 2.

---

## Output

Write to `{output_dir}/register/pocs/`:
- `poc_{ID}.json` — structured exploitation data (schema in `@reference/JSON_SCHEMAS.md`)
- `poc_{ID}.py` — executable Python script inheriting `BasePoC`
