---
name: audit-jndi-lookup
description: Audit endpoints with jndi-lookup capability. Produces jndi-injection findings.
---

# Role

Specialist for **jndi-injection** (including Log4Shell-class). Produces findings with `category_id` = `jndi-injection`,
aligned with the audit-endpoint routing table.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `jndi-lookup` **or
`logging-sink`** (a logged user input is a Log4Shell sink on a vulnerable
log4j2 — same `jndi-injection` category). For the `logging-sink` case the sink
is frequently in a **callee** of the handler (a service/helper method), not the
handler body — follow the call chain into those methods before concluding there
is no logged user input.

# SINK patterns

| Language | SINK |
|---|---|
| Java | `new InitialContext().lookup(user)`, `Context.lookup(user)` where `user` contains `ldap://` / `rmi://` / `dns://` |
| Java | log4j2 `${jndi:ldap://...}` pattern (log4j-core in the Log4Shell range — 2.0-beta9 .. 2.14.1 fully, 2.15.0 partial bypass) triggered via any logged user input -- inspect all `logger.info/warn/error/debug/fatal/trace(...)` and `logger.log(level, ...)` calls, whether the user input is **string-concatenated into the message** (`LOG.info("x=" + user)`) **or passed as a `{}` parameter** (`LOG.info("x={}", user)`) — see the version note below for why both are exploitable |

For each candidate SINK, trace the data flow back to the request entry — the chain must terminate at request param /
header / body / path param, or data carried via state (DB / session / file). The sink is often in a **callee** of the
handler (a service / manager / helper method), not the handler body itself — follow the call chain (read the invoked
method) before concluding there is no logged user input. If the source is a constant or system-controlled value, do not
report it.

**Confirm the log4j2 version** from the dependency manifest (`pom.xml`, `build.gradle`, a bundled `log4j-core-<ver>.jar`,
or CLAUDE.md Stack). A logged user input is only a Log4Shell sink on a vulnerable version; if the version is unknown,
favor recall and report it, naming the uncertainty in the finding.

# Workflow — do these IN ORDER, do not skip step 1

You are frequently dispatched **because of a `logging-sink`** — the Log4Shell
path is your *primary* target, not the classic `InitialContext.lookup`. Do not
let a more visible non-JNDI sink (a shell exec, a file op, a SQL call) in the
same handler distract you; those belong to other skills and are **out of scope
here**. Run this order:

1. **Scan every logging call first.** Grep/read the handler **and every callee
   in the snippet pool** for `logger`/`LOG`/`LOGGER` `.info/.warn/.error/.debug/`
   `.fatal/.trace/.log(...)`. For each, ask: is any argument user-controlled
   (trace it back to a request param / body / header / path, possibly through the
   handler→service call)? `LOGGER.info("Character [" + character + "]")` with
   `character` from the request **is a hit**. This is the single most-missed
   jndi sink — never conclude "no jndi" without having done this scan.
2. **Confirm the engine is log4j2** — `import org.apache.logging.log4j...` /
   `LogManager.getLogger` (NOT slf4j/logback). Then apply the version rule above
   (vulnerable range → report; unknown → report with stated uncertainty).
3. **Then** check classic `InitialContext().lookup(user)` / `Context.lookup(user)`.
4. If step 1 found a user-controlled logged value on log4j2, **emit a
   `jndi-injection` finding** at that logging call (file+line of the
   `LOGGER.x(...)` in the callee). Writing `[]` after seeing such a sink is a
   recall miss — re-check before doing so.

# Safe context (false-positive prevention)

Do NOT report:

- `Context.lookup(constant)` where the JNDI name is a hard-coded string / config-supplied static value
- log4j-core >= 2.17 (lookups disabled by default) or `log4j2.formatMsgNoLookups=true` set in the runtime configuration
- **Slf4j / Logback** (not log4j2) paths — these engines never perform `${jndi:...}` lookups at all, so a logged user
  input is safe regardless of concatenation vs parameterization. **Caution:** do NOT extend this to log4j2. On a
  vulnerable log4j2 the lookup runs against the *fully formatted* message, so a `{}` parameter (`logger.info("x={}", user)`)
  is just as exploitable as concatenation — the "only the format string is parsed" reasoning is false for log4j2.
- SINKs whose argument traces back to a hard-coded constant or system-controlled value

Out-of-scope categories belong to other audit skills — LDAP search filter -> `audit-ldap-query`. If you spot them,
mention them in your report and let the orchestrator dispatch the right specialist; do not file them yourself.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
