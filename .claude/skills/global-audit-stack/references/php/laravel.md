# Laravel Configuration Audit Reference

Used by audit-stack when LANGUAGE=php, FRAMEWORK=laravel. Covers Laravel's middleware pipeline, APP_KEY handling, CSRF protection, session cookie security, CORS configuration, authentication guards, and JWT secret configuration.

## Architecture: Middleware Pipeline

Laravel uses middleware to intercept HTTP requests. Middleware can be applied globally (`$middleware`), per-group (`$middlewareGroups` like `web` and `api`), or per-route (`$routeMiddleware` / `$middlewareAliases`). The `auth` middleware checks whether the user is authenticated before allowing the request through.

Key points to trace:
- **Which routes have the `auth` middleware?** Routes without it are publicly accessible. Check `routes/*.php` and `app/Http/Kernel.php`.
- **Guards** — `config/auth.php` defines guards (session, token, JWT). The default guard is used unless specified. Custom guards may implement weaker validation — trace the `attempt()` or `validate()` method to confirm password verification is performed.
- **APP_KEY** — used for all encryption and signed cookies. If it is empty or committed as a known literal in `.env`, encrypted data can be decrypted and session cookies can be forged.
- **Policies and Gates** — `Gate::define()` and Policy classes handle authorization. Routes that check authentication but not authorization may allow any logged-in user to perform privileged actions.

## Error Handling and Debug Mode

Laravel's exception handler (`app/Exceptions/Handler.php`) controls what users see on errors. In debug mode, Laravel shows full stack traces, environment variables, and request data.

Key points to trace:
- `APP_DEBUG` value in `.env` or `config/app.php` — if `true` in production, error pages expose `APP_KEY`, database credentials, API keys from `.env`, and the full stack trace.
- Custom `render()` methods — do they include `$exception->getMessage()` or `$exception->getTraceAsString()` in the response?

## CSRF Protection Architecture

Laravel's `VerifyCsrfToken` middleware validates a CSRF token on every POST/PUT/PATCH/DELETE request. The token is stored in a cookie and submitted with each form.

Key points to trace:
- `$except` array in `VerifyCsrfToken` — routes listed here skip CSRF validation. Are they listed for a legitimate reason? Do any of them handle state-changing operations?
- The `api` middleware group excludes CSRF by default. If the API uses cookie-based session auth rather than token-based auth, CSRF protection is missing.
- Route-level `withoutMiddleware(VerifyCsrfToken::class)` — same question: why is CSRF disabled?
- The `web` middleware group — confirm it includes `VerifyCsrfToken` and `StartSession`.

## CORS Configuration

Laravel does not ship a built-in CORS middleware before Laravel 7; from 7+ it includes `fruitcake/laravel-cors` (now `laravel/cors`) via `config/cors.php` and the `HandleCors` middleware.

Key points to trace:
- `allowed_origins` in `config/cors.php` — is it set to `['*']`?
- `supports_credentials` — if `true`, the browser will include cookies in cross-origin requests.
- The combination of `allowed_origins=['*']` and `supports_credentials=true` allows any origin to make credentialed cross-origin requests, exposing session cookies.

## Session Architecture

Laravel stores sessions based on `SESSION_DRIVER` (file, database, redis, cookie, array). The session ID is stored in a cookie; the actual data lives server-side (except for the `cookie` driver, which stores everything in the browser encrypted with `APP_KEY`).

Key points to trace:
- `SESSION_DRIVER=cookie` — all session data is in the user's browser, encrypted with `APP_KEY`. If `APP_KEY` is known, the data is readable and modifiable.
- Session cookie attributes in `config/session.php`: `secure` (HTTPS only), `http_only` (no JS access), `same_site` — are all three set for production?
- After login, does the session ID regenerate? Laravel's default `RegenerateSession` middleware handles this, but custom login flows may skip it.

## JWT Configuration

Projects using `tymon/jwt-auth` or similar packages store the JWT signing secret separately from `APP_KEY`.

Key points to trace:
- `JWT_SECRET` in `.env` or `config/jwt.php` — is it a hardcoded literal, or generated and stored securely?
- Token verification settings: `algo`, `leeway`, `required_claims` — any weakening of defaults?

For cross-language JWT misuse patterns (decode vs verify, alg=none), see `global-audit-auth/SKILL.md (JWT section)`.

## Output

- `APP_DEBUG=true` in production `.env` or `config('app.debug')` true in prod → `information-disclosure`
- `APP_KEY` empty or `base64:<HARDCODED>` literal in committed `.env` → `static-key-leak`
- CSRF middleware (`VerifyCsrfToken`) globally disabled or `$except` list overly permissive → `csrf`
- `web` middleware group missing CSRF/session protection → `csrf`
- `config/cors.php` with `allowed_origins=['*']` and `supports_credentials=true` → `cors-misconfiguration`
- Session cookie config missing `secure`/`http_only`/`same_site` in `config/session.php` for prod → `business-logic-flaw`
- Custom auth guard in `config/auth.php` that bypasses password verification → `incorrect-authorization`
- Hardcoded JWT secret in `config/jwt.php` or `tymon/jwt-auth` config → `static-key-leak`
