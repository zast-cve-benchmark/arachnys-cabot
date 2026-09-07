# Express Configuration Audit Reference

Used by audit-stack when LANGUAGE=javascript, FRAMEWORK=express. Covers middleware pipeline ordering, session architecture and cookie security, JWT handling, CORS configuration, and CSRF protection.

## Architecture: Middleware Pipeline

Express middleware is a function with `(req, res, next)` signature. Middleware is registered via `app.use()` or `router.use()` and executes in registration order. Each middleware can modify the request/response, end the response, or call `next()` to pass control to the next middleware.

Key points to trace:
- **Registration order is critical** — `app.use(authMiddleware)` must appear before any route that requires auth. If a route is registered before the auth middleware, that route is unprotected.
- **No global default** — Express has no built-in auth. Every route is public unless middleware explicitly protects it.
- **Custom auth middleware** — middleware that conditionally skips calling `next()` may silently pass requests through unauthenticated. Confirm that the middleware always calls `next()` only after a successful auth check, and terminates (or calls `next(err)`) on failure.
- **Error handling middleware** — identified by having 4 parameters `(err, req, res, next)`. If no error handler is registered, Express sends default HTML error pages that include stack traces in development mode.

## Session Architecture

`express-session` stores session data server-side and a session ID in a cookie. The session ID identifies the user; the server-side data stays private.

Key points to trace:
- What store is used? The default `MemoryStore` is designed for development only — it leaks memory and does not scale.
- Cookie configuration: `cookie.secure` (HTTPS only), `cookie.httpOnly` (no JS access), `cookie.sameSite` — which are set?
- `secret` — where is the session signing secret defined? Is it a hardcoded string literal, or loaded from an environment variable?
- After login, is the session ID regenerated via `req.session.regenerate()`? If not, session fixation is possible.
- `cookieParser` signed cookies use a `secret` argument — if it is a hardcoded literal in source, the signing can be forged.

## JWT in Express

Typically via `express-jwt` or `jsonwebtoken`. `express-jwt` is middleware that extracts the JWT from the `Authorization` header, verifies the signature, and sets `req.user`.

Key points to trace:
- Is `jwt.verify(token, secret)` used, or `jwt.decode(token)`? `decode` only base64-decodes the payload — it performs no signature verification. Any crafted token is accepted.
- Where is the secret defined? Hardcoded in source, or loaded from an environment variable?
- Is `algorithms` specified in the verification options? If omitted, algorithm confusion attacks (including `alg: none`) may be possible.
- Is `ignoreExpiration` set to `true`? If so, expired tokens remain valid.

For cross-language JWT misuse patterns (decode vs verify, alg=none), see `global-audit-auth/SKILL.md (JWT section)`.

## CORS Configuration

Express has no built-in CORS handling. The `cors` npm package is the standard solution: `app.use(cors(options))`.

Key points to trace:
- Is `cors({ origin: '*', credentials: true })` configured? The combination of wildcard origin and credentials is a misconfiguration — it allows any origin to make credentialed cross-origin requests, exposing session cookies to attacker-controlled pages.
- Is the CORS middleware applied globally or only to specific routes? If applied globally with permissive settings, all endpoints are exposed.
- Dynamic `origin` callbacks that reflect the request `Origin` header without validation are equivalent to wildcard.

## CSRF Protection

Express does not include CSRF protection by default. The `csurf` package (now deprecated but still widely used) or `lusca.csrf()` adds token validation to state-changing requests.

Key points to trace:
- Is `csurf` or `lusca.csrf()` mounted via `app.use()` before state-changing route handlers?
- Are `POST`, `PUT`, `PATCH`, `DELETE` routes for sensitive operations (login, profile update, fund transfer) covered by the CSRF middleware?
- Is any route explicitly excluded from CSRF validation that should not be?

## Output

- Hardcoded `JWT_SECRET` / `SESSION_SECRET` / `cookie-secret` constant → `static-key-leak`
- `app.use(cors({ origin: '*', credentials: true }))` or equivalent wildcard + credentials combo → `cors-misconfiguration`
- CSRF middleware (`csurf` / `lusca.csrf`) absent on state-changing routes → `csrf`
- `app.use(session({ cookie: { httpOnly: false } }))` or missing `secure: true` in prod → `business-logic-flaw`
- `jwt.decode(token)` used in place of `jwt.verify(token, secret)` → `incorrect-signature-verification`
- `cookieParser(<HARDCODED_SECRET>)` signed-cookie secret literal → `static-key-leak`
- Custom auth middleware that does not call `next()` based on actual session/token validity → `incorrect-authorization`
