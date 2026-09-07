---
name: audit-password-reset
description: Audit password reset / forgot-password / reset-token endpoints. Produces business-logic-flaw (token replay / takeover) and open-redirection (reset link host-header injection) findings.
---

# Role

Specialist for password-reset flow `business-logic-flaw` and (when applicable) `open-redirection`.

# Trigger recap

Dispatched when identify-business-scenarios returns password-reset.

# SINK patterns

Key points from `logic-vuln-audit/modules/password_reset/step2_sinks.md`:

1. **Token randomness**: using `Math.random()` / auto-increment sequence / timestamp -> predictable
2. **Token long-lived**: no expiry, no one-shot consumption, replayable
3. **Token not bound to user**: user A's token accepted on user B's request
4. **Host header injection**: email link concatenates `Host` header -> attacker can forge mail -> phishing
5. **Email enumeration**: response differs between non-existent and existing email
6. **Missing post-reset side effects**: old sessions cleared? user notified? MFA cleared?
7. **Reset request accepts any old password**: flow logic error (e.g. PUT accepts `oldPassword=null`)

Allowed `category_id` values for this skill: `business-logic-flaw`, `open-redirection`.

# Safe context (false-positive prevention)

- Password-strength (weak hash, plaintext storage) of the newly-set password → handled by `audit-login` or a cross-cutting auditor, not here.
- Account lockout / brute force on the reset endpoint itself is in scope as `business-logic-flaw`; reusing the same hash function as login is not.
- Do not write PoCs in this skill.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
