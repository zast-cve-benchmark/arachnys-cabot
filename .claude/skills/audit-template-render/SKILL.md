---
name: audit-template-render
description: Audit endpoints with template-render capability. Produces ssti findings.
---

# Role

Specialist for **ssti** (server-side template injection) — the template *string* itself is user-controlled (not just user-controlled template variables). Produces findings with `category_id` = `ssti`, aligned with the audit-endpoint routing table.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `template-render`.

# SINK patterns

| Engine | SINK |
|---|---|
| Jinja2 (Python) | `Template(user).render(...)`, `Environment.from_string(user)`, Flask `render_template_string(user)` |
| Django Template | `Template(user).render(Context(...))` (in `django.template`) |
| Freemarker (Java) | `new Template("name", new StringReader(user), cfg)`, `cfg.getTemplate(userPath)` (when userPath is fully user-controlled) |
| Velocity (Java) | `Velocity.evaluate(ctx, writer, "name", user)` |
| Thymeleaf | `TemplateEngine.process(user, context)` (when `user` is the template string).  Also see **implicit view name injection** below — user input reaching the view name via `@Controller` return value or URL path is equally dangerous. |
| Mustache / Handlebars (JS) | `Handlebars.compile(user)(ctx)`, `Mustache.render(user, ctx)` |
| Twig (PHP) | `$twig->createTemplate($user)->render($ctx)` |
| ERB (Ruby) | `ERB.new(user).result(binding)` |
| Smarty (PHP) | `$smarty->fetch("eval:" . $user)` |
| PHP (Blade) | Laravel Blade `{!! $user !!}` (unescaped output) or `Blade::render($user, $data)` with a user-controlled template string; also `view()->make("eval:" . $user)` patterns where the view name is attacker-influenced |

# Safe context (false-positive prevention)

**Sandboxed rendering is NOT SSTI.** A user-controlled template string is only SSTI if it is rendered by an
**unsandboxed** engine. If the template is rendered through a sandbox, the
sandbox IS the control — a user-controlled template alone is then an intended
feature (e.g. user-customizable notification templates), NOT a finding. Do not
report it unless you can demonstrate a concrete sandbox escape.

Treat these as sandboxed (safe) — do not report:
- Jinja2 `jinja2.sandbox.SandboxedEnvironment` / `ImmutableSandboxedEnvironment`
- a project wrapper whose name or module signals safety (`safe_jinja`,
  `safe_render`, `sandboxed_*`) — open the wrapper; if it constructs a
  `Sandbox*Environment` underneath, it is sandboxed
- Twig with the sandbox extension; Liquid (Shopify) which is sandboxed by design

Before writing an SSTI finding, follow the render call into the helper and
confirm the environment is a plain, non-sandboxed one. If it is sandboxed,
drop the finding.

Also out of scope:
- variable values are user-controlled but the template string is a constant — that is XSS or a business-logic issue, not SSTI
- EL / OGNL injection — that belongs to `audit-expression-eval`

# References

When auditing a Spring MVC / Thymeleaf endpoint, read
`references/thymeleaf.md` for implicit view-name injection patterns that do not
involve an explicit `TemplateEngine.process()` call.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
