---
name: audit-code-eval
description: Audit endpoints with code-eval capability. Produces code-injection findings.
---

# Role

Specialist for **code-injection**. Produces findings with `category_id` = `code-injection`, aligned with the audit-endpoint routing table. Scope is strictly "user-controlled string interpreted as code in the host language runtime" (eval / exec / Function constructor / etc.).

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `code-eval`.

# SINK patterns

| Language | SINK |
|---|---|
| Java   | `ScriptEngine.eval(user)`, Groovy `Eval.me(user)`, `GroovyShell.evaluate(user)` |
| Python | `eval(user)`, `exec(user)`, `compile(user, ...)`, `code.InteractiveConsole().runsource(user)` |
| Node   | `eval(user)`, `new Function(user)`, `vm.runInThisContext(user)`, `vm.runInNewContext(user)` |
| Ruby   | `eval(user)`, `instance_eval(user)`, `class_eval(user)`, `module_eval(user)` |
| PHP    | `eval($user)`, `assert($user)`, `create_function($args, $user)` |

For each candidate SINK, trace the data flow back to the request entry — the chain must terminate at request param / header /
body / path param, or data carried via state (DB / session / file). If the source is a constant or system-controlled value,
do not report it.

# Safe context (false-positive prevention)

Do NOT report:

- arguments passed to the SINKs above that are hard-coded literals or sanitized AST nodes
- SSTI / template-engine string evaluation — that belongs to `audit-template-render`
- expression-language injection (SpEL / OGNL / MVEL / JEXL) — that belongs to `audit-expression-eval`

`code-eval` strictly means "code string in the host language runtime". Anything that uses a separate sub-language engine
(template / EL / XPath) is out of scope.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run the per record-vulnerabilities Steps 1-2.
