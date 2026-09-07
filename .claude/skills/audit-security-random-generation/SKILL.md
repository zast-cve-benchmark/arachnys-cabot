---
name: audit-security-random-generation
description: Audit endpoints that generate random values for security-sensitive use. Produces insecure-random findings.
---

# Role

Specialist for `insecure-random` — endpoints that generate session IDs, tokens, OTPs, salts, etc. using non-cryptographic RNG.

# Trigger recap

Dispatched when identify-business-scenarios returns security-random-generation.

# SINK patterns

**Insecure random:**

1. `Math.random()` (Java/JS) used for token / session ID / nonce / OTP / password salt
2. Python `random.*` (not `secrets.*`) used in security contexts
3. `Random()` (PHP < 7) / `mt_rand()` used for tokens
4. `rand()` / `srand()` (C/PHP) used for token / key derivation
5. Timestamp used as token (`System.currentTimeMillis()` / `time.time()`)

Allowed `category_id` values for this skill: `insecure-random`.

# Safe context (false-positive prevention)

- Random values used for **non-security purposes** — e.g. UI placeholder colors, animation seeds, sampling/jitter in retry backoff, A/B test bucketing, log correlation IDs that don't gate access — are not security-sensitive; do not report.
- A token derived from a weak RNG but then **passed through a one-way cryptographic primitive** (HMAC-SHA256, PBKDF2, scrypt) **with a properly random key** is no longer attacker-predictable from the output.
- `SecureRandom` / `java.security.SecureRandom` / `secrets.token_*` / `crypto.randomBytes` / `random_bytes()` (PHP 7+) are cryptographically secure; do not report.
- Weak JWT algorithm / signing-key handling → `audit-login`, not here.
- Do not write PoCs in this skill.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
