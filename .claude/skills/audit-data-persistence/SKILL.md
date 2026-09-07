---
name: audit-data-persistence
description: Audit endpoints that persist user input. Tracks stored / second-order flows where the dangerous sink fires in a different code path (worker / scheduled task / sibling endpoint). category_id depends on downstream sink: sql-injection / ssti / xpath-injection / ssrf / xss / etc.
---

# Role

Specialist for stored / second-order vulnerabilities — endpoint persists attacker-controllable data, and the dangerous downstream operation lives elsewhere (background worker / scheduled task / async queue consumer / recheck flow), forming the vulnerability.

First-order auditors (`audit-url-access`, `audit-xpath-eval`, etc.) only cover the case "sink is visible inside this endpoint handler's call graph". This skill fills their blind spot: **source is at this endpoint, sink is elsewhere across storage**.

# Trigger recap

Dispatched when identify-business-scenarios returns data-persistence. Often runs alongside audit-crud or audit-profile-update.

# SINK patterns

Unlike first-order auditors, this skill's pool (the master-built `SNIPPETS_FILE`) only contains the **handler + first-level callees** — the source side. Downstream sink code is **not in the pool**; you must locate it yourself via Glob/Grep/Read.

## Mandatory enumeration discipline (must read; failures here cause silent CVE drops)

Before any other step, **enumerate every user-controllable field** the handler
persists. List them by name in your thinking. Do this **first**, before deciding
which is "interesting". Common drift mode: model zooms in on one exotic field
and silently drops well-known dangerous fields next to it (a URL field, a
filename field, etc.).

Then for each persisted field **independently**:

1. Apply the sieve below to keep dangerous-shape fields
2. Trace its downstream sink
3. **Write one finding per field × undefended sink branch** (not one finding total)

A handler that persists, say, a URL + a filter-expression field + a body-text
field typically produces **at least 3 findings** if all three are unvalidated:
SSRF (URL → outbound fetch by a worker), xpath-injection / el-injection
(filter expression → evaluator), and SSTI / stored XSS (body text → renderer).
Producing only one finding on such a handler is almost always a recall miss
— the typical drift is to fixate on the most exotic-looking field and skip
the others.

**Multi-engine dispatch on a single field is multi-finding, not one.** When
one persisted field is dispatched downstream by prefix or type tag to multiple
evaluators (e.g. one branch reaches an XPath evaluator, another reaches a
general-purpose expression engine), write **one finding per undefended
branch** — see "Scoping" below.

## Dangerous-shape sieve (only trace "dangerous-shape" persisted data — key to controlling divergence)

Forward cross-codebase tracing easily diverges. **After enumerating all
persisted fields above**, run this sieve and keep only "dangerous-shape"
fields; discard the rest.

**Category 1 — Injection-carrier values (judged by value type):**
- Free-text string -> rendered into HTML downstream means **stored XSS**
- URL -> **SSRF**; if scheme is controllable or `file://` is allowed -> **LFI / arbitrary file read**
- File path / file name -> **path traversal / LFI**
- Template string -> **SSTI**
- Expression / filter / query / selector (XPath, JSONPath, jq, SQL, EL, CSS selector ...)
  -> **corresponding injection**

**Judging a field's type must be evidence-based, not guesswork from the field name.** A field's form definition / validator / label /
docstring often states its type directly — a typed list-of-strings form field
whose label or validator name mentions any of the expression-engine vocabulary
(CSS, JSONPath, jq, XPath, SQL, template, regex, etc.) is an explicit
"expression / filter carrier", regardless of how the variable itself is named.
**Any persisted field whose name, label, validator, or comment contains words like
filter / selector / expression / query / rule / xpath / jsonpath / jq / sql /
template must be kept as dangerous-shape, and traced first to its evaluation / execution
sink** (XPath evaluator, general-purpose expression engine, `eval()`,
template render, ...) — these fields are this agent's highest-yield targets.
Never discard them as plain text or treat them as XSS-only just because "the
value looks like an ordinary string".

**Category 2 — Data that affects system behavior (judged by storage location):**
- Attacker-writable global templates, global configs, settings that affect environment/runtime — blast radius is
  system-level (global SSTI, behavior tampering, sensitive info leakage)

**Skip (non-injection carriers, do not trace):** booleans, numeric IDs, enums, timestamps, internal flags.

## Method (strictly follow these 5 steps)

1. **List fields**: from the handler, list persisted fields and the structure
   they're written into (record / DB table / file / global config object).
2. **Sieve**: apply the "dangerous-shape sieve" above and **keep only dangerous-shape fields**, discard the rest. If no field survives the sieve
   -> write 0 findings and stop.
3. **Find readers**: for each kept field / global item, Grep/Read the whole
   codebase yourself to find its **read sites** — dict/index access on the
   stored record (`record["<field>"]` / `record.get("<field>")`), ORM
   attribute access (`obj.<field>`), corresponding ORM query, file read,
   config read.
4. **Trace to sink**: for each read site, follow 1-2 hops to see if the data flows into a **sensitive-capability sink** —
   `http-request` (`requests.*` / `session.request` / `urllib` / `httpx`),
   eval / code / template / xpath / jq / sql / EL injection family, `archive-extract`,
   file read, environment variable read, etc. Follow until the **first undefended** sensitive sink; do not exhaust all read sites
   — for the determination of "undefended" and "sinks with built-in defenses don't count" see "Safe context" below;
   when one field is dispatched by content to multiple different evaluators, report one per branch — see the "Scoping" note below.
5. **Review two lines of defense**: after hitting a sink, before writing the finding, confirm both defenses in order:
   - **Whether the sink itself has built-in defense** — sandboxed template engines (Jinja2
     `ImmutableSandboxedEnvironment` / `SandboxedEnvironment`, Twig sandbox,
     Liquid), parameterized / prepared queries, auto-escaping HTML context, etc. If the sink has built-in defense
     and you can't produce a concrete bypass, **that sink is not a vulnerability** (see "Safe context" below).
   - **Source-side validation / sanitization before storing** — is it sufficient.
   If either line of defense is sufficient, do not report; only write a finding if both are insufficient or missing.

## Expression / query injection — hard decision rule (weak models must follow this verbatim; do not argue about whether the evaluator is safe)

When a user-controllable persisted field flows into an XPath / XQuery / jq / JSONPath / SQL / EL / OGNL
or similar **expression / query evaluator**, the decision rests on one thing only — **does the source side have a "dangerous-function-level"
restriction**:

- The source side only does **syntax / compile validation** (`Validate*Input`, `jq.compile()`,
  `elementpath.select()` trial-compile..., only confirms the expression "parses")
  -> **judge it injection directly and write a finding**; pick `category_id` from the corresponding legal enum value: XPath ->
  `xpath-injection`; SQL -> `sql-injection`; Java EL / SpEL -> `el-injection`;
  OGNL -> `el-injection`; **jq / JSONPath / other general-purpose expression engines -> `el-injection`**
  (CWE-917 expression-language injection, covering non-Java expression evaluators). **Do not write
  values not in the enum like `expression-injection` / `jq-injection` — they will be silently
  dropped by the orchestrator.**
- The source side has an **explicit dangerous-function blacklist / whitelist or a restricted evaluation context** -> only then may you not report.

**Do not go on to argue "does this evaluator have dangerous built-in functions" or "will the result be visible to the attacker" —
that is the wrong direction of exoneration; weak models almost always reason wrongly at this step.** The facts: expression evaluators commonly
can read files / read env / read stdin (XPath has `unparsed-text()` / `doc()`; jq has `env` /
`$ENV`), and scraping-type tools commonly snapshot filter results and echo them back. **Syntax / compile validators are not
sanitizers** — they only confirm the expression "parses", not restrict "what it can do".

`category_id` for this skill is the category of the SINK you reached — this skill crosses categories by following the data flow. Use whichever fits the sink: `ssrf`, `insecure-file-read`, `path-traversal`, `xpath-injection`, `ssti`, `xss`, `sql-injection`, `el-injection`, `code-injection`, `prompt-injection`, etc.

Each finding's `data_flow` **must contain both** the source endpoint's storage point and the downstream sink point (write out `file#Lx` locations for both ends) to reflect the complete cross-storage data flow.

# Safe context (false-positive prevention)

When tracing hits a sink, first judge whether it is one of the following "built-in defense" shapes; if so, **it is not a vulnerability, do not write a finding**:

- **Sandboxed template rendering** — Jinja2 `ImmutableSandboxedEnvironment` /
  `SandboxedEnvironment`, Twig sandbox, Liquid. Arithmetic / string /
  built-in filters / extensions allowed inside the sandbox (e.g. `arrow.now()`, `regex_replace`) **are intended functionality, not
  SSTI**. **Once you recognize the renderer is a sandbox engine, judge that sink safe and stop immediately** — do not
  dig into sandbox implementation, engine version, known CVEs, or escape techniques: sandbox-escape research is not this skill's
  responsibility, and that depth will blow the time budget. Treat it as safe directly and continue tracing the next sink for that field.
- **Auto-escaped HTML context** — after `markupsafe.escape()`, `html.escape()`,
  autoescape-enabled template variables, `htmlspecialchars()`, it is not XSS.
- **Parameterized / prepared queries** — placeholder-bound SQL / ORM queries are not SQL injection.

**Key: a "built-in defense" sink does not consume the "stop at first sink" budget — it doesn't count;
continue tracing the next sink along the same field until you hit a truly undefended sink or exhaust the budget.**
For example, a field flows first into sandboxed Jinja (doesn't count), then into `requests.request` (SSRF, counts) —
report the latter, do not stop at the former.

## Scoping (control divergence — especially important for weak models)

- Only trace "dangerous-shape" fields (see sieve above); do not go back to fields you skipped.
- Stop at the first **undefended** sensitive sink per field; do not exhaust (sinks with built-in defenses don't count and
  do not terminate tracing).
- **Exception — when one field is dispatched by content to multiple different evaluators, report one per branch.** If a field's
  value is dispatched by prefix / type tag to **different** evaluators (e.g.
  a prefix dispatcher routes one branch to an XPath evaluator and another
  branch to a general-purpose expression engine), these branches are
  independent sinks, and you should **write one finding per undefended branch**, not subject to the "stop at first sink"
  limit. This is not exhaustion — the upper bound is the number of evaluators the field actually dispatches to.
- Trace depth 1-2 hops.
- **If you cannot establish a full source->sink chain within budget, do not write a finding** — do not produce "to-be-reviewed"
  half-baked output.

## Boundaries

- vs `audit-crud`: the latter audits the CRUD operations themselves (IDOR, authorization bypass,
  mass-assignment); this skill audits "downstream usage of stored data". Both often run together.
- vs first-order skills like `audit-url-access` / `audit-xpath-eval`: those audit the first-order case where "the sink is visible inside this
  endpoint handler's call graph"; this skill audits the case where "the sink is not in the handler's call graph,
  reached cross-component via storage". Occasional overlap on the same category between the two is acceptable; the orchestrator merges them.
- Do not write PoCs in this skill.

# References (Read on demand)

- **Quartz / scheduled tasks** — if the endpoint stores a job definition
  (`invokeTarget` / `jobClass` / `methodParams`, e.g. `/monitor/job/add`,
  `/schedule/job/*`), Read `references/quartz-scheduled-task.md`: the scheduler
  executes the stored target later (deferred). Grep for the executor
  (`JobInvokeUtil` / `getBean` / `invokeMethod`) — it is not in the pool.

  **An invoke-by-name reflective sink has NO single fixed category — emit one
  finding PER reachable impact class.** The stored string names *what to invoke*,
  and the attacker chooses it, so the one sink simultaneously enables every class
  reachable through the resolved bean/class/method: `code-injection` (invoke an
  arbitrary `bean.method(args)`), `jndi-injection` (target a bean that performs a
  JNDI/LDAP/RMI lookup on an argument), `insecure-deserialization` (target a
  deserializer fed an attacker arg), and `sql-injection` (target a method that
  runs attacker-influenced SQL). Do NOT collapse to a single category and stop —
  write a separate finding for each impact class the resolved-target machinery
  can plausibly reach (a denylist like "blocks `rmi://`" or "class name must
  contain >1 dot" is bypassable and does not remove a class). This is the general
  rule for any reflective dispatch-by-name sink, not a single framework.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
