---
name: audit-url-redirect
description: Audit endpoints with url-redirect capability. Produces open-redirection findings.
---

# Role

Specialist for **open-redirection**.

# Trigger recap

Dispatched when identify-sensitive-capabilities returns `url-redirect`.

# SINK patterns

| Language | SINK |
|---|---|
| Java | `response.sendRedirect(user)`, Spring `RedirectView(user)` / `"redirect:" + user`, `ResponseEntity.status(302).header("Location", user).build()` |
| Python | Flask `redirect(user)`, Django `HttpResponseRedirect(user)`, FastAPI `RedirectResponse(url=user)` |
| Node | Express `res.redirect(user)` |
| PHP | `header("Location: " . $user)` |
| Go | `http.Redirect(w, r, user, http.StatusFound)` |

The sink takes a user-controlled URL (or URL fragment) and emits it as the
`Location` header. The `user` argument can be either the direct redirect
target OR a *prefix / base* that is concatenated with a fixed suffix —
prefix-controlled redirects still pivot to `//attacker.example/...`
(protocol-relative) or `https://attacker.example/...`.

# Route A — Direct user-input redirect

The handler's `redirect(...)` argument is built from a request parameter
visible in this endpoint (path / query / body / header). Standard case;
match against the SINK table above and decide if there's a defense.

# Route B — Middleware-injected redirect base (do NOT skip)

The handler's `redirect(...)` argument uses a value the handler **did not
compute itself** — e.g. `res.redirect(res.locals.baseHref + 'subpath')`,
`return redirect(g.host_prefix + path)`, `response.sendRedirect(model.base
+ "/x")`. The value comes from a **global request-scoped store** that some
upstream middleware / catch-all route populated.

This is the load-bearing pattern for "all `/foo/*` routes share the same
open-redirect bug" CVEs. The handler-only snippets the worker received do
not show the middleware; the worker **must Grep for it**.

## Mandatory middleware sweep

When the redirect argument references a shared / request-scoped variable
(`res.locals.*`, `req.<custom>`, `g.*`, request attributes, model
attributes, framework filter outputs, etc.) whose origin is not visible in
the handler snippets, run the following sweep:

1. Identify the shared-state name being read in the handler (e.g.
   `res.locals.baseHref`, `g.base_url`, `req.contextPrefix`).
2. Grep the codebase for **writes** to that name. Hit patterns by stack:

   | Stack | Where the writer typically lives |
   |---|---|
   | Express / Koa / Connect | `app.use(fn)`, `router.use(fn)`, `app.all('*', fn)`, `router.all('*', fn)`, `appRouter.all('*', fn)`, `app.param(...)`. Look for `res.locals.<name> = ...` / `req.<name> = ...` inside. |
   | Flask | `@app.before_request`, `@blueprint.before_request`. Look for `g.<name> = ...` / `request.<name> = ...` writes. |
   | Django | `MIDDLEWARE` setting; classes with `process_request` / `__call__`. Look for `request.<name> = ...` writes. |
   | Spring / Servlet | `OncePerRequestFilter.doFilterInternal`, `HandlerInterceptor.preHandle`, `@ControllerAdvice` + `@ModelAttribute`, servlet `Filter.doFilter`. Look for `request.setAttribute(...)` / model writes. |
   | Echo / Gin / Chi / Fiber / Mux | `e.Use(...)`, `e.Pre(...)`, `r.Use(...)`, `app.Use(...)`, `router.Use(...)`. Look for `c.Set(name, ...)` / `c.Locals(name, ...)` / context-value writes. |

3. **Inside the writer**, check whether the assigned value derives from
   request input — `req.originalUrl`, `req.url`, `req.get('Referer')`,
   `req.headers.host`, `req.protocol`, query strings, path params, or any
   chain that ultimately reads from `req` / `request`.

4. **Confirm the link**: handler reads the same name in `redirect(...)`
   AND the writer derives from request input AND there is no validation /
   allowlist in either spot → **open-redirection finding** at this
   endpoint. The `data_flow` should include both the writer line (in the
   middleware file) and the redirect line (in this handler).

This sweep MUST run whenever the redirect target references shared state.
Do not exclude on the grounds that "the middleware is not in my snippets"
— the middleware is structurally invisible to handler-scoped audits, and
ignoring it is the exact failure mode that causes recall misses on every
endpoint under such a router.

Exclude: allowlist / relative-path-only / redirect only after hostname validation.

# Safe context (false-positive prevention)

Do NOT report:

- Redirects whose target traces back to a hard-coded constant or system-controlled value
- Redirects guarded by an allowlist that validates the destination host (not just the format)
- Redirects restricted to relative paths only (no `://`, no protocol-relative `//host`)
- Redirects only fired after explicit hostname validation against trusted origins

**A note on "starts with `/`" defenses.** A common but insufficient check is
`if (target.startsWith('/')) redirect(target)`. **This does NOT defend
against `//attacker.example/path`** — that string starts with `/` and
the browser treats it as protocol-relative. To exclude, the defense must
also reject leading `//` (or use a parser that confirms the URL is a
relative path with no authority component).

Out-of-scope categories belong to other audit skills — outbound HTTP requests (SSRF)
-> `audit-url-access`. If you spot them, mention them in your report and let the
orchestrator dispatch the right specialist; do not file them yourself.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
