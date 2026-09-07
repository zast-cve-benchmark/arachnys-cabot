# Profile Update PoC Generation Guide

## Objective

Generate executable Proof-of-Concept code for all confirmed profile update vulnerabilities identified in `vulnerability_analysis.json`, leveraging the business logic context from `business_logic.json`.

## Input

- `business_logic.json` -- business logic analysis results
- `vulnerability_analysis.json` -- confirmed vulnerability findings

---

## Task Requirements

### 1. Exploitability Analysis

For each vulnerability, answer:

- Can this vulnerability be triggered externally (client-controllable parameters)?
- What preconditions are needed (account, permissions, specific state)?
- What is the technical difficulty (easy / medium / hard)?
- What indicates successful exploitation?
- What is the impact scope (single account / batch accounts / system-wide)?

### 2. Exploitation Step Design

- Decompose the attack into clear, sequential steps
- Ensure logical consistency between steps
- Use response data from earlier steps in subsequent requests
- Define concrete actions, not vague descriptions
- Specify: request parameters, expected response, success criteria

### 3. PoC Code Standards

- **Language**: Python with `requests` library
- **Parameterized**: Target URL, credentials, and identifiers must be configurable
- **Error handling**: Include exception handling and result verification
- **Output**: Print execution status and results at each key step
- **Runnable**: Code must execute without modification beyond configuration
- **Commented**: Clear comments explaining each step

---

## Common Exploitation Patterns

### IDOR Exploitation

```
1. Authenticate as attacker (User A)
2. Capture a legitimate profile update request
3. Replace the user identifier (user_id / account_id) with victim's (User B)
4. Submit the modified request
5. Verify: query User B's profile to confirm unauthorized modification
```

### Parameter Tampering / Mass Assignment

```
1. Authenticate as a normal user
2. Send a standard profile update request
3. Inject additional fields (role, is_admin, credits, balance, vip_level)
4. Verify: check if the injected fields were persisted
```

### Privilege Escalation via Mass Assignment

```
1. Authenticate as a low-privilege user
2. Send profile update with privilege fields (role=admin, is_admin=true)
3. Verify: confirm privilege elevation by accessing admin-only resources
```

### Password Change Without Old Password

```
1. Authenticate (or reuse a stolen session)
2. Send password change request without old_password field
3. Verify: log in with the new password
```

### Session Persistence After Password Change

```
1. Authenticate and save the session token (Token A)
2. Change the password via the profile update endpoint
3. Use Token A to make an authenticated request
4. Verify: if the request succeeds, the old session was not invalidated
```

---

## Exploit Chain Consideration

When multiple vulnerabilities exist, evaluate whether they can be combined:

- IDOR + Mass Assignment = modify another user's privilege fields
- Username Enumeration (via SINK 8 error leakage) + IDOR = targeted attacks
- Frontend Bypass + Missing Verification = change sensitive fields without checks

---

## Output

Write PoC files to `{output_dir}/profile_update/pocs/`:
- `poc_{ID}.json` — structured exploitation data
- `poc_{ID}.py` — executable Python script inheriting `BasePoC`

Schema: see `@reference/JSON_SCHEMAS.md` § poc_output.

> **Note**: Do NOT produce exploit chain files here. Exploit chains are handled by the Chain & Reporter Agent in Phase 5.

---

## Accuracy Requirements

- PoC must be grounded in the actual code logic from the analysis -- no baseless assumptions
- HTTP requests (format, parameters, headers) must match the real application endpoints
- Data passed between steps must follow the observed business logic flow
