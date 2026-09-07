---
name: audit-expression-eval
description: Audit endpoints with expression-eval capability. Produces findings categorized by the engine's reachable impact — information-disclosure / el-injection / code-injection / others.
---

# Role

Specialist for **server-side expression-language evaluators where the
expression string itself is user-controlled** (NOT the case where only the
bindings inside a fixed expression are user-controlled — that is XSS or a
business-logic issue, file in other skills).

## Category selection — specific over broad

The single most important rule of this skill: **the `category_id` must
match the engine's actually-reachable impact, not the broadest applicable
bucket.**

`el-injection` is reserved for engines that are RCE-capable (SpEL, MVEL,
JEXL, JSP EL, and the like). Engines that cannot RCE get a more specific
category that reflects what they *can* do:

| Engine reachable impact | `category_id` |
|---|---|
| Reads env / exfiltrates secrets, result echoed | `information-disclosure` |
| Reads arbitrary files | `insecure-file-read` (use `path-traversal` if the engine surface is path-style / direction ambiguous; use `code-injection` if the engine can execute the file it reads) |
| Triggers outbound HTTP | `ssrf` |
| Invokes shell / processes | `command-injection` |
| Loads / invokes arbitrary classes (Java) or evaluates host code | `code-injection` (Java) **OR** `el-injection` if the engine is in the SpEL/MVEL/JEXL/JSP-EL family |
| Full RCE via a Java EL-family engine | `el-injection` |
| OGNL on a default context | `el-injection` (OGNL maps to `el-injection`; see `references/ognl.md`) |

When in doubt, **Read the engine's reference file** under `references/`
and pick the category from its "Decision rules" section. Each per-engine
reference is authoritative for its engine.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `expression-eval`.

# Workflow

1. **Identify the engine.** From the snippets / handler / referenced
   library imports, determine which expression evaluator is involved:
   jq, JSONPath, SpEL, OGNL, MVEL, JEXL, JSP EL, or something else.

2. **Read the matching reference.** Each engine has its own file under
   `references/`. Read the one that matches:

   | Engine | Reference |
   |---|---|
   | jq (Python `jq`, Go `gojq`, Node `node-jq`) | [references/jq.md](references/jq.md) |
   | JSONPath (`jsonpath-ng`, `JayWay JsonPath`, …) | [references/jsonpath.md](references/jsonpath.md) |
   | Spring Expression Language | [references/spel.md](references/spel.md) |
   | OGNL (Struts2 / MyBatis) | [references/ognl.md](references/ognl.md) |
   | MVEL | [references/mvel.md](references/mvel.md) |
   | Apache Commons JEXL | [references/jexl.md](references/jexl.md) |
   | JSP / Jakarta EL | [references/jsp-el.md](references/jsp-el.md) |

   For an engine not on the list, follow the **general workflow** below.

3. **Determine if the expression is user-controlled.** This can be either:
   - **Route A — Direct evaluation in this handler.** The handler (or a
     function in its call graph during this request) takes a user-supplied
     string and passes it to the engine's `compile()` / `parseExpression()`
     / `eval()` / `createExpression()` API.
   - **Route B — Stored expression → background evaluation.** The handler
     persists a user-supplied expression into storage; a worker /
     scheduled task / sibling endpoint later loads the stored value and
     passes it to the engine. Confirm by Grep on the field name; if a
     downstream reader compiles / evaluates the stored value, **the
     vulnerability is in scope at this endpoint** (the storage end).
   - **Route C — Multi-engine prefix / type dispatch.** A persisted field
     is dispatched by prefix or type tag to multiple evaluators. When one
     branch reaches an expression engine in this skill's scope, that
     branch is an independent finding for the corresponding engine — write
     one finding per branch.

4. **Apply the reference's "Decision rules" to pick `category_id`.** Do
   not pick `el-injection` by default — pick the specific category the
   reference points to. If the reference says "not a finding" for the
   present configuration (e.g. a sandboxed or restricted-context engine),
   write 0 findings.

5. **`data_flow` must include both ends.** For Route A: handler entry +
   sink line. For Route B: handler storage line + downstream evaluator
   line. The orchestrator uses both to drive verification.

# General workflow for engines without a reference file

When you encounter an expression engine not covered by `references/`:

1. Read the engine's public docs or its host-language sink line to figure
   out what it can actually do — env access, file I/O, network, reflection,
   shell, class loading.
2. Pick `category_id` based on the **highest-impact capability the engine
   reaches**, using the table at the top of this file.
3. If the engine is general-purpose and RCE-capable (i.e. it has unrestricted
   reflection or `eval`-like host integration), use `el-injection`.
4. If the engine is data-only (filtering / path navigation / arithmetic) and
   has env-read or cross-record-read potential, use `information-disclosure`.
5. After you successfully audit a new engine, consider whether a future
   audit would benefit from a `references/<engine>.md` writeup; if yes,
   leave a `// TODO add reference for <engine>` note in your final report
   (no need to write it yourself in this pass).

# Hard decision rule — compile-only validation is NOT a sanitizer

The single most common false negative is treating "the validator
successfully compiled the user expression" as proof of safety. **A compile
check only confirms the expression parses; it does not restrict what the
expression can do at runtime.**

Rule, verbatim:

- If the source-side validation is **only** syntax / compile validation,
  proceed to report the finding. Use the category the engine's reference
  file dictates.
- The source side is only "safe" when it imposes a **dangerous-capability
  restriction**: an explicit deny-list of dangerous identifiers, an
  allow-list of permitted constructs, OR a restricted evaluation context
  (sandboxed engine, frozen binding map, denied host access). The
  engine-specific reference describes what counts as a real restriction
  for that engine.

# Boundaries

- Template-engine cases where the *template string itself* is user-controlled
  → `audit-template-render`, not this skill.
- XPath / XSLT / LDAP / SQL / NoSQL expression languages — file in their
  own skills (`audit-xpath-eval`, `audit-xslt-transform`, `audit-ldap-query`,
  `audit-sql-query`).
- The expression string is hard-coded; only the *variable bindings* inside
  it are user-controlled. That is XSS or business-logic, not handled here.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
