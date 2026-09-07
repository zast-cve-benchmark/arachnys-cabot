---
name: global-audit-auth
description: Project-wide audit of authentication + authorization mechanisms. Foundation-layer skill always dispatched by global-audit. Covers JWT misuse, session/cookie security, password storage KDF, OAuth/OIDC flows, project-level authz design. NOT per-endpoint sink-level checks.
---

# global-audit-auth

You audit how the project does authentication and authorization at the foundation level. Framework-agnostic — applies regardless of Shiro/Spring Security/Django/Passport/etc.

## Scope

In scope (this skill):
- JWT use: signature verification, alg choice, key strength, expiry, key storage
- Session management: cookie attrs, session fixation, idle timeout, regeneration on login
- Password storage: KDF choice (BCrypt cost, PBKDF2 iterations, Argon2 params), salting
- OAuth / OIDC flow: state param, PKCE, redirect_uri validation, scope handling
- Project-level authorization design (e.g., entire endpoint class has no @RequiresPermissions)

Out of scope:
- Framework-specific filter chain config (e.g., Shiro filterChainDefinitions, Spring Security httpSecurity) — that's `global-audit-stack`
- Structural bugs in custom auth filter / token util (return-true for OPTIONS, non-constant-time compare) — that's `global-audit-stack/<framework>` if framework-contract-dependent, otherwise `global-audit-security-components`
- Per-endpoint IDOR / missing-check — that's `audit-endpoint`

## JWT

The single most common foundation-level auth bug. Six patterns to check whenever the project imports a JWT library:

### Pattern 1: decode without verifying
A method named `getIssuer` / `getSubject` / `parseClaims` that internally calls a decode-only JWT API reads attacker-controlled claims as if they were signature-checked.

- Java (java-jwt): `JWT.decode(token)` returns `DecodedJWT` without verifying — `getIssuer()/getSubject()` read from untrusted payload. Safe: `JWT.require(algorithm).build().verify(token)`.
- Java (jjwt, `io.jsonwebtoken`): the safe terminal call is `parseClaimsJws(token)` / `parseSignedClaims(token)` — it REQUIRES a signed JWS and verifies the signature. `parse(token)` and `parseClaimsJwt(token)` are UNSAFE **even when `setSigningKey(...)` is present**, because they also accept unsigned (`alg:none`) tokens and never enforce a signature — a forged/unsigned token passes. The tell is the terminal method (`parseClaimsJws`/`parseSignedClaims` = safe; `parse`/`parseClaimsJwt` = unsafe), NOT whether a signing key was supplied. Both `Jwts.parser()...parse(token)` and the builder form `Jwts.parserBuilder().setSigningKey(k).build().parse(token)` have this bug.
- JavaScript (jsonwebtoken): `jwt.decode(token)` is decode-only. Safe: `jwt.verify(token, secret)`.
- JavaScript (jose): `decodeJwt(token)` is decode-only. Safe: `jwtVerify(token, key)`.
- Go (jwt-go / golang-jwt): `jwt.Parse(token, keyFunc)` does verify when keyFunc returns a key. Watch for `keyFunc` returning `nil` or for the `alg: none` accepted in keyFunc.
- Python (pyjwt): `jwt.decode(token, options={"verify_signature": False})` bypasses verification. Safe: omit options or set `verify_signature=True`.
- PHP (firebase/php-jwt): Older versions had `JWT::decode($token, $key, false)` (third arg bypasses) — check version.

Grep:
```
grep -rn "JWT\.decode\|jwt\.decode\|decodeJwt\|jwt\.Parse\b" <project-root>/src
# jjwt: any token-validation method — terminal parseClaimsJws/parseSignedClaims = safe, parse()/parseClaimsJwt = unsafe even with setSigningKey
grep -rn "Jwts\.parser\|parserBuilder\|parseClaimsJwt\|parseClaimsJws\|parseSignedClaims" <project-root>/src
grep -rn "verify_signature.*False" <project-root>
```

For each match, Read the surrounding method. If the result is used to derive `userName` / `userId` / `role` and passed to authentication / authorization downstream, it's a vuln.

### Pattern 2: alg=none accepted
Some libraries accept `alg: none` if the verifier doesn't explicitly require an algorithm. Check that signature verification specifies the expected algorithm.

### Pattern 3: weak / shared / leaked signing key
- HMAC key < 32 bytes (256 bits) for HS256, < 48 for HS384, < 64 for HS512
- Default key in source/config that users don't change (see Trust boundary judgment below)
- Same key across environments

### Pattern 4: token expiry missing or trivial
- `withExpiresAt(new Date())` issues an already-expired token → developer probably meant something else
- No expiry at all → tokens never expire, lost token = forever access
- Refresh token without rotation → similar risk

### Pattern 5: claim trust
- Trusting `iss` / `aud` / `sub` without verifying it matches expected values
- Using a key derived from a claim (key confusion)

### Pattern 6: not validating cross-token replay
- Same JWT accepted indefinitely → no jti / nonce tracking for high-value operations

## Sessions

If the project uses traditional sessions instead of (or alongside) JWT:

- Cookie missing `HttpOnly` flag → XSS can steal session
- Cookie missing `Secure` flag → cleartext leak on HTTP fallback
- Cookie missing `SameSite=Strict` or `SameSite=Lax` → CSRF surface
- No session regeneration after login → session fixation
- Eternal session timeout
- Session ID generated from predictable RNG (cross-ref `global-audit-crypto`)

Grep for cookie / session config:
```
grep -rn "Set-Cookie\|setCookie\|cookieBuilder" <project-root>/src
grep -rn "session_cookie_httponly\|session_cookie_secure\|SESSION_COOKIE" <project-root>
```

## Password storage

- bcrypt cost factor < 12 (2026 baseline) → vuln
- PBKDF2 iterations < 600,000 (OWASP 2023) → vuln
- Argon2id with very low memory/time → vuln
- SHA-256 / SHA-512 / MD5 directly for password (no KDF) → vuln (cross-ref `global-audit-crypto`)
- Raw password compared via `String.equals` or similar → timing side-channel (cross-ref `global-audit-security-components`)

Grep:
```
grep -rn "BCryptPasswordEncoder\|BCrypt\.hashpw\|bcrypt\.gensalt" <project-root>
grep -rn "PBKDF2\|pbkdf2_hmac" <project-root>
```

For each, check the strength parameter.

## OAuth / OIDC (if present)

- Missing `state` parameter in authorization request → CSRF
- Missing PKCE for public clients → code interception
- `redirect_uri` not strict-matched against allowlist → open redirect via OAuth
- Implicit flow used for SPAs → token leakage (auth code + PKCE is current best practice)

## Project-level authorization design

Scan for **broad-stroke** authorization issues, not per-endpoint:
- A whole controller / blueprint / module without any auth decorator (e.g., `AdminController` with no `@RequiresPermissions` on any method)
- A decorator that's applied inconsistently across CRUD operations for the same resource
- Role check based on user-controlled input (e.g., `if request.headers["X-Role"] == "admin"`)

## Auth secrets (JWT signing keys, OAuth client secrets, session encryption keys)

Trust boundary judgment (apply to any auth-related hardcoded secret):
- Who SHOULD know this secret? Who can ACTUALLY obtain it?
- Open-source / self-hosted: default secret is a vuln if users typically don't rotate it (e.g., HMAC key for JWT in `application.yml`)
- Enterprise internal: any hardcoded secret is a vuln

Grep:
```
grep -rn "jwt\.secret\|jwt\.key\|signing.key\|client.secret\|session.secret" <project-root>
```

For each, check whether the value is loaded from env / vault or hardcoded as a default.

## Output

| Pattern | category_id |
|---|---|
| JWT decode-without-verify / alg=none / claim trust without verify | `incorrect-signature-verification` |
| JWT signing key hardcoded with leakable scope | `static-key-leak` |
| OAuth client secret hardcoded / session encryption key hardcoded | `static-key-leak` |
| Default or weak login credentials (default admin password, easily guessable accounts) | `weak-credentials` |
| Cookie missing HttpOnly / Secure / SameSite | `business-logic-flaw` |
| Password stored without strong KDF / weak cost | `insecure-crypto-configuration` |
| Broad-stroke missing authorization on admin controller | `incorrect-authorization` |
| OAuth missing state / PKCE / strict redirect_uri | `csrf` (state), `business-logic-flaw` (PKCE), `open-redirection` (redirect_uri) |

## Anti-Hallucination Rules

- ✗ Do NOT judge a function by its name — `getIssuer` does NOT mean "verify then get issuer"
- ✗ Do NOT report JWT decode-no-verify without confirming the decoded claim flows into authentication/authorization
- ✗ Do NOT report short HMAC key as vuln without measuring (bytes, not chars)
- ✓ MUST Read both the JWT call site AND the consumer that uses the decoded claim
- ✓ For jjwt, judge by the TERMINAL call, not the presence of `setSigningKey`: `parse()`/`parseClaimsJwt()` do not require a signature even with a key set — only `parseClaimsJws()`/`parseSignedClaims()` do
- ✓ MUST verify the cookie attributes by reading the actual set-cookie code, not assuming defaults

Core principle: **Better to miss than to false-positive.**

## Output format

Write findings as a flat JSON array `[ {...}, ... ]` of `SimpleVulnInfo`. See `record-vulnerabilities` for the schema and the mandatory `validate_vulns.py` step. Empty findings → write `[]` (still valid).

No per-endpoint issues — focus on GLOBAL / project-wide defects only.
