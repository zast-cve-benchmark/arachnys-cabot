---
name: global-audit-crypto
description: Project-wide audit of cryptographic algorithm / mode / key / IV / salt / RNG usage. Foundation-layer skill always dispatched by global-audit. Looks for broken algorithms (MD5/SHA-1/ECB/RSA<2048), hardcoded crypto keys, predictable RNGs used as security values, and custom signing/HMAC helpers with subtle defects.
---

# global-audit-crypto

You audit the project's cryptographic use: which algorithms, which modes, which keys, which RNGs. Framework-agnostic — applies to any web stack.

## Scope

In scope (this skill):
- Hash function choice (MD5, SHA-1 used for password / signing)
- Cipher algorithm + mode (DES, 3DES, RC4, AES-ECB, fixed IV/salt, RSA<2048)
- RNG choice for security-sensitive values (Java `java.util.Random`, Python `random`, Node `Math.random`, Go `math/rand`)
- Hardcoded crypto keys / salts / IVs in source or config (anything fed to `SecretKeySpec`, `KeyGenerator`, `Cipher.init`, `Mac.init`, etc.)
- KDF use for password storage (BCrypt cost factor, PBKDF2 iterations, Argon2 params)

Out of scope:
- JWT signing keys / OAuth secrets — that's `global-audit-auth`
- Generic API token / DB password — that's `global-audit-config`
- Structural bugs in custom signing utility (non-constant-time compare, HMAC over subset) — that's `global-audit-security-components`

## Scan checklist

### Java
```
grep -rn "MessageDigest\.getInstance\(\"MD5\|SHA-?1\"" <project-root>/src
grep -rn "Cipher\.getInstance\(\"\(DES\|RC4\|.*ECB.*\)\"" <project-root>/src
grep -rn "new IvParameterSpec\|new SecretKeySpec" <project-root>/src
grep -rn "\bjava\.util\.Random\b\|new Random\(" <project-root>/src
grep -rn "DigestUtils\.\(md5\|sha1\)" <project-root>/src
grep -rn "KeyPairGenerator.*\"RSA\"" <project-root>/src   # check keysize call nearby
```

### Python
```
grep -rn "hashlib\.\(md5\|sha1\)\|MD5\|SHA1" <project-root>
grep -rn "Crypto\.Cipher.*MODE_ECB\|AES\.new.*MODE_ECB" <project-root>
grep -rn "import random\|from random import" <project-root>
grep -rn "PBKDF2\|bcrypt\.gensalt" <project-root>  # check param strength
```

### JavaScript / Node
```
grep -rn "crypto\.createHash\(['\"]md5\|['\"]sha1" <project-root>
grep -rn "createCipheriv.*['\"]aes-..-ecb" <project-root>
grep -rn "Math\.random()" <project-root>  # if used for token/id, flag
```

### Go
```
grep -rn "md5\.\|sha1\.\|crypto/md5\|crypto/sha1" <project-root>
grep -rn "\bmath/rand\b" <project-root>   # crypto/rand should be used instead for security
grep -rn "des\.NewCipher\|rc4\.NewCipher" <project-root>
```

### Cross-language: hardcoded crypto keys
Look for string literals fed to `SecretKeySpec`, `AES.new(key=...)`, `createCipher(_, key, _)`, etc. Heuristic: long base64/hex literals near variable names like `key`, `secret`, `iv`, `salt`, `aes`.

```
grep -rn "SecretKeySpec\|new IvParameterSpec" <project-root>/src
```

Trace each match: is the byte array passed in a literal, or loaded from env/keystore?

## Judgment rules

**Trust boundary (apply to every hardcoded crypto key found):**
- Who SHOULD know this key? Who can ACTUALLY obtain it?
- Open-source / self-hosted project: default keys are common; vuln only if (a) production deployments are unlikely to rotate it OR (b) it ships with the same default everywhere
- Enterprise internal: any hardcoded crypto key is a vuln (should be in vault/KMS/env)
- If users are forced to set it at deploy time (no working default), it's not a vuln

**Algorithm choice:**
- MD5 / SHA-1 for any security purpose (password hashing, signing, MAC, integrity over untrusted input) → vuln
- DES / 3DES / RC4 / RSA<2048 / DSA → vuln
- AES-ECB → vuln (deterministic, leaks patterns)
- Fixed IV with CBC → vuln (defeats IV purpose)
- Fixed salt for password hashing → vuln (defeats salt purpose)

**RNG:**
- `java.util.Random` / Python `random` / Node `Math.random` / Go `math/rand` used to generate session ID, token, salt, key, nonce → vuln
- Same RNGs used for non-security-sensitive values (UI shuffling, sampling) → not a vuln

## Output

| Pattern | category_id |
|---|---|
| Broken hash (MD5/SHA-1) used for password/signing | `insecure-crypto-configuration` |
| AES-ECB / fixed IV / fixed salt / weak cipher mode | `insecure-crypto-configuration` |
| RSA<2048 / DSA / DES / 3DES / RC4 | `insecure-crypto-configuration` |
| Hardcoded crypto key fed to `SecretKeySpec` / `AES.new` / etc. | `insecure-crypto-configuration` (and also `static-key-leak` if leakable) |
| Predictable RNG used for security-sensitive value | `insecure-random` |
| Hardcoded AES/HMAC key/salt/IV with leakable scope | `static-key-leak` |

## Anti-Hallucination Rules

Every finding MUST be based on actual code you have Read.
- ✗ Do NOT guess file paths
- ✗ Do NOT fabricate code snippets
- ✗ Do NOT judge an algorithm by the import name alone — confirm by reading the call site
- ✗ Do NOT report a hardcoded key as vuln without checking it's not just a placeholder constant the user is forced to override

- ✓ MUST Read a file before reporting anything about it
- ✓ MUST quote actual code in the description

Core principle: **Better to miss than to false-positive.**

## Output format

Write findings as a flat JSON array `[ {...}, ... ]` of `SimpleVulnInfo`. See `record-vulnerabilities` for the schema and the mandatory `validate_vulns.py` step. Empty findings → write `[]` (still valid).

No per-endpoint issues — focus on GLOBAL / project-wide defects only.
