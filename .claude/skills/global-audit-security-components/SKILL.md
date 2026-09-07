---
name: global-audit-security-components
description: Project-wide audit of the project's own custom security components (filter / interceptor / middleware / token util / crypto wrapper / realm / auth provider). Foundation-layer skill always dispatched by global-audit. Uses DEPTH-FIRST reading (not API blacklist grep), looking for structural / control-flow / contract-misuse bugs in code the project wrote itself.
---

# global-audit-security-components

You audit the project's **own** security code — the filters, interceptors, middlewares, token utilities, crypto wrappers, custom realms, etc. that the project wrote itself (NOT third-party library use). You operate in **depth-first read mode**, not pattern grep mode: you OPEN files, read them whole, and reason about control flow and contracts.

## Why this sub-skill exists

The other foundation sub-skills (crypto / auth / config) are **API blacklist scanners**: they grep for known dangerous APIs and check usage. They catch pattern-instance bugs ("you called MD5", "you wrote `JWT.decode` instead of verify").

This sub-skill catches a different bug class: **structural / control-flow / contract bugs** that pattern grep cannot find. Examples:
- A custom signing utility uses correct HMAC but compares signatures via `String.equals` (timing attack)
- A token util has correct verify() but the calling code only checks `!= null` and not the verification result
- A custom rate limiter checks IP from a header that's attacker-controlled
- A state machine for password reset has an out-of-order transition

You CANNOT find these by grepping for API names. You have to read the code.

## Locate target files

Glob the project for security-relevant components. Use multiple naming conventions because projects vary:

```
find <project-root>/src -type d \
  \( -name "security" -o -name "auth" -o -name "filter" \
     -o -name "interceptor" -o -name "middleware" -o -name "shiro" \
     -o -name "session" \)
find <project-root>/src -name "*Security*" -o -name "*Auth*" \
  -o -name "*Filter*" -o -name "*Token*" -o -name "*Sign*" \
  -o -name "*Crypto*" -o -name "*Cipher*" -o -name "*Realm*"
```

For each match: Read the whole file. Don't skim.

## The six Socratic questions (apply to every function you read)

Every function is a trust boundary. Apply each question in order:

1. **Clarify** — What does this function actually do, line by line? Read its source.
2. **Question assumptions** — What does it assume about its input (format, presence, value range)?
3. **Probe evidence** — Where does this input come from? Trace to origin (request param, header, DB read, config).
4. **Challenge perspectives** — Is there another control-flow path that reaches this with different input?
5. **Examine consequences** — If an assumption breaks, what happens? Does the failure mode fail open or closed?
6. **Reflect** — Am I distracted by an obvious issue while missing a subtler one nearby?

## Specific recurring traps (check explicitly when reading auth / token / signing code)

These four trap classes are foundation-level and frequently missed:

### Trap 1: Token "decode" used where "verify" is needed
A method named `getIssuer` / `getSubject` / `parseClaims` that internally calls a *decode-only* API (e.g. `JWT.decode`, `jwt.decode`, `decodeJwt`, `jwt.Parse` without a key func). The caller treats the result as authenticated → trivial forgery.

(This is also covered in `global-audit-auth/SKILL.md`'s JWT section as Pattern 1. Both worker can flag it; not a problem.)

### Trap 2: Missing token expiry check
Custom verification that does not call `withExpiresAt` / equivalent, or that issues tokens with `new Date()` as the expiry, yields tokens that never expire (or are pre-expired but the verifier doesn't check).

### Trap 3: Custom HMAC over a subset of fields
A signature utility that hashes only some of the request fields (or hashes fields in non-canonical order) lets the attacker mutate the unsigned fields freely.

Read the signing function carefully:
- Are ALL security-relevant fields hashed?
- Are field separators present (no ambiguity from concatenation)?
- Is the key positioned correctly (HMAC vs naive `H(msg || key)` — the latter has length-extension issues with Merkle-Damgård hashes)?

### Trap 4: Non-constant-time secret comparison
Comparing MACs / tokens / hashes with `==` / `String.equals` / `Objects.equals` / `compareTo` short-circuits on first mismatching byte. Over remote connections this leaks the secret byte-by-byte via response timing.

Safe APIs:
- Java: `MessageDigest.isEqual(a, b)`
- Python: `hmac.compare_digest(a, b)`
- Node: `crypto.timingSafeEqual(a, b)`
- Go: `crypto/subtle.ConstantTimeCompare(a, b)`

### Trap 5: Auth filter that lets requests through without enforcing the check
Read the project's own auth `Filter` / interceptor / middleware `doFilter` /
`preHandle` body end-to-end and ask: **on the protected paths, is there any way
`chain.doFilter(...)` / `return true` / `next()` is reached without a successful
authentication/authorization check?** Tells:
- The filter computes an auth result but **never acts on it** — falls through to
  `chain.doFilter(req, res)` unconditionally (no `return` / no 401 on failure).
- A bypass branch keyed on attacker-controllable input — a `User-Agent` /
  header / path check that grants a pass (e.g. trusting a `serverIdentity`
  header, or skipping auth for a path prefix an attacker can match).
- The filter is registered but its URL pattern doesn't actually cover the
  sensitive endpoints (registration gap).

A servlet filter whose `doFilter` unconditionally calls `chain.doFilter` on a
path that should require auth is a **missing-authorization** flaw for every
endpoint it fronts — report `incorrect-authorization` (scope: application, or the
specific endpoint set it guards). This is *absence of enforcement*, so there is
no sink line — point at the filter's pass-through. (Recognizing a
framework-contract bug — Shiro `onAccessDenied` returning `true` — instead needs
`global-audit-stack`; this trap is the framework-agnostic "computed-but-unused /
unconditional pass-through" case.)

## Scheduled-task invokeTarget reflection RCE

Quartz / scheduled-job frameworks let an admin store a string that names the method to run, then a job executor reflects on that string to invoke it. If the stored string is attacker-influenced (e.g. via a job-add/job-edit controller), the executor is a **stored → reflection RCE sink** — a persisted `invokeTarget` like `beanName.method('arg')` is later turned into a live call. Find and trace this chain:

```
grep -rn "JobInvokeUtil\|invokeMethod\|invokeTarget\|SchedulerFactory\|@Scheduled\|createScheduleJob" <project-root>/src
```

For each match, Read the executor and check whether it takes the stored `invokeTarget` string and resolves it to a callable via reflection — `Class.forName(...).newInstance()`, `Method.invoke(...)`, or Spring `applicationContext.getBean(beanName)` followed by `method.invoke(...)`. That is the sink.

Then trace the source: find the job-add / job-edit controller that **persists** `invokeTarget` (e.g. `/monitor/job/add`). If user-supplied `invokeTarget` can reach the reflective executor without an allowlist on the target bean/class+method, report it as `code-injection`. An "invokeTarget validation" that only blocks a few denylisted package prefixes is bypassable — treat denylist-only filtering as still vulnerable.

## Non-HTTP deserialization sinks (RPC / socket / Netty / queue)

The HTTP endpoints aren't the only attack surface. Many projects expose a
**non-HTTP** inbound channel the project itself implements — a custom RPC server,
a Netty pipeline, a raw socket protocol, a message-queue consumer — that reads an
attacker-controllable frame and **deserializes** it. These are systematically
missed because no per-endpoint worker reaches them.

Grep for the project's own inbound-frame decoders / consumers, then read whether
the payload bytes hit an unsafe deserializer:

```
grep -rn "deserialize\|deSerialize\|readObject\|ObjectInputStream\|Hessian\|Kryo\|FurySerializer\|Fury\b\|@RabbitListener\|@KafkaListener\|channelRead\|MessageToMessageDecoder\|ByteToMessageDecoder" <project-root>/src
```

For each, check whether the deserializer is fed bytes that arrive from the
network/queue without a type allowlist or a safe codec. A custom
`*Serializer.deSerialize(byte[])` (Fury/Hessian/Kryo/Java-native) on an RPC frame
whose class/type is attacker-chosen is `insecure-deserialization` (RCE class), even
though there is no HTTP endpoint. Report it scoped to the handler/decoder.
(Best-effort: tracing a non-HTTP frame to its origin is harder than an HTTP
handler; when the source is plausibly remote-controlled and the codec is unsafe,
report it and state the reachability assumption.)

## Boundary with global-audit-stack

Some bugs in custom security code require **framework-contract knowledge** to recognize (e.g., Shiro's `AccessControlFilter.onAccessDenied` returning `true` means "grant access" — without knowing Shiro you can't judge whether `return true` is a bug). Those belong in `global-audit-stack/<framework>` references, not here.

This skill catches structural / generic-pattern bugs that don't require framework-contract knowledge:
- Wrong use of HMAC / hash
- Non-constant-time compare
- Missing null checks that lead to bypass
- State-machine errors in auth flows
- Trusting request-controlled inputs (header X-Forwarded-For for IP-based auth, etc.)

## Output

Findings can use any `category_id` from `SimpleVulnInfo`, but most common:
- `incorrect-authorization` (custom auth filter bypass)
- `incorrect-signature-verification` (custom token util issue)
- `insecure-crypto-configuration` (custom signing util issue)
- `business-logic-flaw` (state machine / control-flow issue)

## Anti-Hallucination Rules

- ✗ Do NOT report based on file name alone (`SecurityConfig.java` may be perfectly safe)
- ✗ Do NOT judge a method by its name — `verifyToken` may not actually verify
- ✗ Do NOT fabricate code snippets — quote real source

- ✓ MUST Read the entire file (not just function signatures)
- ✓ MUST trace caller and callee for any function flagged
- ✓ MUST distinguish "looks suspicious" from "I can describe a concrete attack" — only report the latter

Core principle: **Better to miss than to false-positive.**

## Output format

Write findings as a flat JSON array `[ {...}, ... ]` of `SimpleVulnInfo`. See `record-vulnerabilities` for the schema and the mandatory `validate_vulns.py` step. Empty findings → write `[]` (still valid).

No per-endpoint issues — focus on GLOBAL / project-wide defects only.
