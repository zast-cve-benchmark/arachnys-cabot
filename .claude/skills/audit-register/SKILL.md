---
name: audit-register
description: Audit register endpoints. Produces business-logic-flaw findings related to registration flow (username-uniqueness bypass, missing email verification, mass-assignment of role, missing rate limit, reserved-account overwrite, weak activation token, implicit login).
---

# Role

Specialist for registration-flow `business-logic-flaw`.

# Trigger recap

Dispatched when identify-business-scenarios returns register.

# SINK patterns

Key points from `logic-vuln-audit/modules/register/step2_sinks.md`:

1. **Username-uniqueness bypass**: case differences (`Admin` vs `admin`), Unicode homoglyphs, trailing whitespace trimmed
2. **Missing email verification**: user can register any email, no magic-link verification
3. **Settable role field**: registration body accepts `role=admin` directly (mass-assignment)
4. **Missing CAPTCHA / rate limit**: scripts can bulk-register
5. **Reserved-account overwrite**: if a username is already held (e.g. "admin"), does registration overwrite it?
6. **Activation token**: weak randomness (user ID + timestamp), long-lived, reusable
7. **Implicit login**: successful registration issues a session token directly — bypassing any future MFA setup
8. **Unrestricted self-registration is itself a broken-access-control flaw.** Before auditing the *quality* of registration, ask whether this endpoint should accept anonymous registrations **at all**. Flag it as a finding when an unauthenticated caller can create an account and the application is **not** a public-signup product — tells: it is an internal / admin / back-office system (an admin console, ops dashboard, enterprise tool), registration is reachable with no invite token / approval step / domain allowlist / admin-only guard, or the created account immediately carries privileged or operational access. (Spring admin frameworks often ship a `/register` that should be disabled in production — open registration = anyone grants themselves an account.) This is the *absence* of a gate, so there is no sink to point at — point the finding at the registration handler itself.

Allowed `category_id` values for this skill: `business-logic-flaw`. (Open/unrestricted registration per item 8 is reported as `business-logic-flaw`; its access-control impact is equivalent to an `incorrect-authorization` label on the same endpoint.)

# Safe context (false-positive prevention)

- Password-strength checks live in the registration flow, but when they yield `insecure-random` style findings they belong to a cross-cutting auditor, not here.
- Weak hash / plaintext storage of the freshly-set password → cross-cutting auditor or `audit-login`, not here.
- Do not write PoCs in this skill.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
