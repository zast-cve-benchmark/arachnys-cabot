# Password Reset PoC Generation Guide

## Purpose

Guide the generation of executable Proof-of-Concept code for all confirmed password reset vulnerabilities. PoCs must be grounded in the actual business logic analysis and vulnerability findings from previous steps, never based on assumptions.

---

## Input

- The business logic analysis JSON (from step 1)
- The vulnerability analysis JSON (from step 2)

---

## Task

1. **Understand the root cause** of every confirmed vulnerability (business or code logic flaw)
2. **Derive step-by-step exploitation procedures** from the attacker's perspective
3. **Generate executable PoC code** for each vulnerability (Python with `requests`)
4. **Identify exploit chains** where multiple vulnerabilities combine for greater impact

---

## Exploitability Analysis Requirements

For each vulnerability, answer:

- Can this vulnerability be triggered externally via client-controlled parameters?
- What prerequisites are needed (account, permissions, specific application state)?
- What is the technical difficulty (easy / medium / hard)?
- What indicates successful exploitation (observable success markers)?
- What is the impact scope (single account / batch accounts / system-wide)?

---

## Exploitation Step Design

- **Step decomposition**: Break the attack into clear, ordered steps
- **Logical completeness**: Ensure correct causal links between steps
- **Reproducibility**: Steps must produce stable, repeatable results
- **Data chaining**: Later steps must use data returned by earlier steps
- **Specificity**: Each step must describe exact request parameters, expected responses, and success criteria

---

## PoC Code Standards

- **Language**: Python using the `requests` library
- **Parameterized**: Target URL, usernames, and other key values must be configurable variables
- **Error handling**: Include exception handling and result verification
- **Output**: Print execution status and results at key steps
- **Runnable**: Code must be copy-paste executable
- **Commented**: Clear comments explaining what each section does

---

## Technique Patterns

### Token Prediction Techniques

When SINK-03 (predictable token) is confirmed:

- **Timestamp-based prediction**: Capture server time from response headers, generate candidate tokens using the same algorithm
- **Sequential pattern detection**: Request multiple tokens, analyze for sequential or patterned generation
- **Weak hash reversal**: If tokens use `MD5(userId)` or similar, compute candidates from known user identifiers
- **Seed recovery**: If a weak PRNG is used, collect enough outputs to recover the seed and predict future tokens

### Multi-Step Reset Flow Exploitation

When SINK-06 (unauthorized reset) or SINK-07 (step bypass) is confirmed:

- **Step skipping**: Directly call the final password update endpoint without completing verification
- **Parameter injection**: Substitute the target user's identifier at the password update step while using your own valid token
- **State manipulation**: Modify client-side state flags that the server trusts to track step completion
- **Flow reordering**: Send requests out of sequence to bypass server-side step validation

### Timing Attack Patterns

When SINK-01 (user enumeration) is confirmed via timing differences:

- **Statistical timing**: Send multiple requests for existing and non-existing users, compute mean response times
- **Baseline establishment**: Measure response times for known-existing and known-nonexistent accounts
- **Threshold determination**: Define a timing delta threshold that reliably distinguishes the two cases
- **Noise reduction**: Use multiple samples and discard outliers for reliable enumeration

### Concurrent Request Exploitation

When SINK-12 (concurrent request anomaly) is confirmed:

- **Race condition**: Send parallel reset requests using threading or async to generate multiple valid tokens
- **SMS/email bombing**: Replay the send-code endpoint concurrently to bypass per-request rate limits
- **State confusion**: Exploit unsynchronized state updates to create inconsistent server-side conditions

---

## Exploit Chain Construction

When multiple SINKs are confirmed, evaluate combinations:

| Chain Pattern | SINKs Combined | Attack Goal |
|--------------|---------------|-------------|
| Enumerate + Brute Force | SINK-01 + SINK-02 | Confirm valid accounts, then brute force their reset codes |
| Enumerate + Predictable Token | SINK-01 + SINK-03 | Confirm accounts exist, then predict their reset tokens |
| Leak + Replay | SINK-08 + SINK-14 | Capture leaked credentials, replay to reset password |
| Bypass + Unauthorized Reset | SINK-07 + SINK-06 | Skip verification, reset arbitrary user's password |
| Concurrent + No One-Time Use | SINK-12 + SINK-05 | Generate multiple tokens, reuse them after partial reset |

For each chain, generate a single combined PoC that executes the full attack sequence end-to-end.

---

## Verification Requirements

- **Success markers**: Define exactly what proves the exploit worked (e.g., login with new password succeeds)
- **Failure diagnostics**: Describe likely failure causes and how to troubleshoot
- **Side effects**: Document any observable impact (account lockout, log entries, notification emails)

---

## Output

Write PoC files to `{output_dir}/password_reset/pocs/`:
- `poc_{ID}.json` — structured exploitation data
- `poc_{ID}.py` — executable Python script inheriting `BasePoC`

Schema: see `@reference/JSON_SCHEMAS.md` § poc_output.

> **Note**: Do NOT produce exploit chain files here. Exploit chains are handled by the Chain & Reporter Agent in Phase 5.
