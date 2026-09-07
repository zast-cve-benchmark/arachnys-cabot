# Koa Configuration Audit Reference

Used by audit-stack when LANGUAGE=javascript, FRAMEWORK=koa. Covers the onion-model middleware pipeline, cookie-signing key security, CORS configuration, CSRF protection, JWT middleware configuration, and session cookie security.

## Architecture: Onion Model Middleware

Koa middleware uses async/await with an "onion model" — each middleware wraps the downstream handler, then unwraps on the way back up. `app.use(async (ctx, next) => { /* before */; await next(); /* after */ })`.

Key points to trace:
- **Middleware registration order** — auth middleware must be registered before route handlers that require it. Because Koa has no built-in auth, every route is public by default.
- **`unless` bypass** — JWT middleware is commonly configured with `koa-jwt`'s `unless({ path: [...] })` to skip validation for public paths. Paths listed here skip JWT validation entirely. Confirm that none of those paths expose sensitive operations.
- **Missing `await next()`** — if an auth middleware fails to call `await next()` on success, the request silently terminates without reaching the route handler. Conversely, if it always calls `await next()` regardless of auth outcome, it is a pass-through.

## Cookie-Signing Keys

Koa uses `app.keys` to sign cookies. Signed cookies are validated via `ctx.cookies.get('name', { signed: true })`.

Key points to trace:
- Is `app.keys = ['<HARDCODED_VALUE>']` a string literal in source? If so, anyone with the source can forge signed cookies.
- Is `app.keys` set at all? If not, `ctx.cookies.set` with `{ signed: true }` throws at runtime, but the fallback may allow unsigned cookies.
- Is key rotation implemented (multiple entries in `app.keys`)? Koa uses the first key for signing and accepts any key for verification — old keys should be rotated out.

## CORS Configuration

`koa-cors` (or `@koa/cors`) adds CORS headers. Common configuration: `app.use(cors({ origin: '*', credentials: true }))`.

Key points to trace:
- Is `origin: '*'` combined with `credentials: true`? This combination is a misconfiguration — the wildcard origin is forbidden when credentials are included, but a misconfigured proxy or custom CORS handler may not enforce this.
- Dynamic `origin` functions that return the request's `Origin` header without validation are equivalent to a wildcard.
- Is CORS middleware placed before route middleware to ensure it applies to all responses including error responses?

## CSRF Protection

Koa does not include CSRF protection by default. `koa-csrf` adds token validation.

Key points to trace:
- Is `koa-csrf` (or equivalent) mounted via `app.use()` before state-changing route handlers?
- Are routes that handle `POST`, `PUT`, `PATCH`, `DELETE` for sensitive operations covered by CSRF validation?
- Is any route excluded from CSRF validation that should not be?

## JWT Middleware

JWT validation in Koa is typically done via `koa-jwt` (which wraps `jsonwebtoken`) or a custom middleware using `jsonwebtoken` directly.

Key points to trace:
- Is `jwt.verify(token, secret)` used, or `jwt.decode(token)`? `decode` only base64-decodes the payload — it performs no signature verification. Any crafted token is accepted as valid.
- Where is the secret defined? Hardcoded string literal in source, or loaded from an environment variable?
- Is `algorithms` restricted in the verify options? If not, algorithm confusion attacks (including `alg: none`) may be possible.

For cross-language JWT misuse patterns (decode vs verify, alg=none), see `global-audit-auth/SKILL.md (JWT section)`.

## Session Cookie Security

Koa has no built-in session management. Common libraries are `koa-session` and `koa-generic-session`. Cookie attributes must be configured explicitly.

Key points to trace:
- Are `httpOnly: true`, `secure: true`, and `sameSite: 'lax'` (or `'strict'`) set in the session middleware options?
- Is `secure` conditionally set based on environment, or forced to `false`/absent in a production config?
- Is session duration (`maxAge`) set to a reasonable value?

## Output

- `app.keys = ['<HARDCODED>']` cookie-signing keys hardcoded → `static-key-leak`
- `koa-cors` / `@koa/cors` with `origin: '*'` and `credentials: true` → `cors-misconfiguration`
- `koa-csrf` absent on state-changing routes → `csrf`
- Custom JWT middleware using `jwt.decode` rather than `jwt.verify` → `incorrect-signature-verification`
- Session middleware without `httpOnly` / `secure` cookie flags in prod → `business-logic-flaw`
- JWT `unless({ path: [...] })` list includes paths that expose sensitive operations → `incorrect-authorization`
