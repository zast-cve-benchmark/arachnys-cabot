---
name: audit-login
description: Audit login endpoints. Produces incorrect-authentication / incorrect-signature-verification / static-key-leak / weak-credentials / business-logic-flaw findings covering JWT algorithm confusion, signing key leaks, weak passwords, session fixation, MFA bypass, brute force, OAuth callback validation, and user enumeration.
---

# Role

Specialist for authentication vulnerabilities in login flows: JWT signature bypasses, hardcoded/weak signing keys, weak or default credentials, and authentication-flow logic flaws.

# Trigger recap

Dispatched when identify-business-scenarios returns login.

# SINK patterns

Key points from `logic-vuln-audit/modules/login/step2_sinks.md`:

1. **JWT algorithm selection**: `alg=none` accepted; inconsistent HS256 / RS256 validation → `incorrect-signature-verification`
2. **JWT no-signature / decode-only call**: `JWT.decode()`, `jwt.decode()`, `parseClaimsJwt()`, or any API that reads claims without verifying the signature → `incorrect-signature-verification`
3. **Hardcoded or weak JWT signing key**: static string in source or config used as HMAC/RSA key → `static-key-leak`
4. **JWT issuance**: excessive or missing expiration (weak token lifetime / replay window) → `incorrect-authentication`; sensitive claims carried in plaintext → information-disclosure, outside this skill's auth scope — defer to a cross-cutting / information-disclosure auditor
5. **Password comparison**: plaintext storage / weak hash (MD5 / SHA1) → `weak-credentials`; default or guessable login password → `weak-credentials`
6. **Session fixation**: session ID unchanged before and after login → `incorrect-authentication`
7. **MFA bypass**: token issued before MFA validation completes → `incorrect-authentication`
8. **Login brute force**: no failure limit / missing captcha → `incorrect-authentication`
9. **Auth side effects not handled**: failure to clear suspicious sessions or stale cookies after successful login → `incorrect-authentication`
10. **Third-party/OAuth callback validation**: missing state validation, missing redirect_uri allowlist → `incorrect-authentication`
11. **API key / Bearer token**: hardcoded with leakable scope → `static-key-leak`
12. **Error message leakage**: "user not found" vs "wrong password" enables user enumeration → `incorrect-authentication`

Category assignment summary:
- JWT `alg=none` / decode-without-verify / no-signature-check / claim-trust-without-verify → `incorrect-signature-verification`
- Hardcoded / weak JWT signing key (or any auth signing key) → `static-key-leak`
- Weak / default login password, plaintext / MD5 / SHA1 password storage → `weak-credentials`
- Session fixation, MFA bypass, OAuth state + redirect_uri, user enumeration, brute-force-no-lockout → `incorrect-authentication`
- Anything that is genuinely a business-logic flaw in the login flow (not fitting above) → `business-logic-flaw`

Allowed `category_id` values for this skill: `incorrect-authentication`, `incorrect-signature-verification`, `static-key-leak`, `weak-credentials`, `business-logic-flaw`.

# Safe context (false-positive prevention)

- Password reset flow → handled by `audit-password-reset`, not here.
- Registration flow → handled by `audit-register`, not here.
- Password-strength / hash-algorithm issues that are purely cross-cutting (e.g. shared crypto util used everywhere) → defer to a cross-cutting auditor rather than reporting here.
- Do not write PoCs in this skill.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
