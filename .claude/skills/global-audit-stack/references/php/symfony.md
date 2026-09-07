# Symfony Configuration Audit Reference

Used by audit-stack when LANGUAGE=php, FRAMEWORK=symfony. Covers Symfony's security firewall architecture, access control rules, CSRF protection, debug mode, CORS configuration, APP_SECRET handling, and custom authenticators.

## Architecture: Security Firewalls

Symfony's security configuration (`security.yaml` / `security.xml`) defines firewalls, providers, and access control rules. Each HTTP request matches exactly one firewall based on URL pattern. The firewall determines how authentication works for that URL space.

Key points to trace:
- **Firewall coverage** — does every sensitive URL pattern match a firewall? URLs that do not match any firewall use the default behavior, which may be no authentication.
- **`anonymous: true`** (Symfony 4/5) or `lazy: true` (Symfony 6+) — firewalls with this setting allow unauthenticated requests through. Whether they reach sensitive routes depends on `access_control`.
- **Authenticators** — custom authenticators replace built-in ones. Trace the `authenticate()` method to confirm it properly validates credentials and does not short-circuit on missing or malformed input.

## Access Control Rules

`access_control` in `security.yaml` defines which roles are required for which URL paths. Rules are evaluated in order; the first match wins.

Key points to trace:
- **Rule ordering** — an overly broad earlier rule (e.g., `path: '^/'` with `roles: PUBLIC_ACCESS`) may shadow a later restrictive rule for an admin path.
- Paths not covered by any rule may be accessible without authorization.
- `IS_AUTHENTICATED_ANONYMOUSLY` or `PUBLIC_ACCESS` on admin paths — intended or misconfiguration?
- Regex patterns with lookahead or optional segments that inadvertently match more paths than intended.

## Error Handling and Debug Mode

Symfony's error detail depends on `APP_ENV` and `APP_DEBUG`. The WebProfilerBundle provides a detailed debug toolbar and profiler at `/_profiler/`.

Key points to trace:
- `APP_DEBUG=1` in production — the profiler exposes request details, routing, database queries, executed commands, and logs.
- Is `/_profiler/` or `/_wdt/` accessible in production? The `web_profiler` routes should not be loaded in prod.
- Custom exception event listeners — do they include internal details (exception message, trace) in the HTTP response body?

## CSRF Protection

Symfony provides CSRF protection via the `csrf_protection` config, integrated into form types via `CsrfTokenManager`.

Key points to trace:
- `framework.csrf_protection.enabled: false` in `config/packages/framework.yaml` — CSRF disabled globally. What is the reason?
- Custom form types that set `csrf_protection: false` on the form options — do they handle state-changing operations?
- AJAX endpoints for state-changing operations — do they validate CSRF tokens explicitly via `$csrfTokenManager->isTokenValid()`?

## CORS Configuration

Symfony does not ship built-in CORS handling. `nelmio/cors-bundle` is the de-facto standard.

Key points to trace:
- `allow_origin: ['*']` in `nelmio_cors` configuration — wildcard origin.
- `allow_credentials: true` — allows the browser to include cookies in cross-origin requests.
- The combination of `allow_origin: ['*']` and `allow_credentials: true` allows any origin to make credentialed cross-origin requests.
- Are CORS rules scoped to API paths only, or applied globally?

## APP_SECRET and Credential Handling

`APP_SECRET` is used to generate CSRF tokens, signed URLs, and remember-me cookies. It must be a unique, unpredictable string per installation.

Key points to trace:
- `APP_SECRET` defined as a literal string in `.env` committed to version control rather than injected from a secrets manager.
- Using the Symfony default sample secret (`ThisTokenIsNotSoSecretChangeIt` or similar).
- Other credentials in `config/packages/*.yaml` — are database passwords or API keys hardcoded or resolved from environment variables?

## Output

- `APP_ENV=prod` with `APP_DEBUG=1` → `information-disclosure`
- `security.yaml` firewalls with `anonymous: true` reaching sensitive routes → `incorrect-authorization`
- `access_control` rules with overly permissive path patterns or `IS_AUTHENTICATED_ANONYMOUSLY` on admin paths → `incorrect-authorization`
- CSRF token check disabled in form configuration or `framework.csrf_protection.enabled: false` → `csrf`
- `nelmio_cors` with `allow_origin: ['*']` and `allow_credentials: true` → `cors-misconfiguration`
- Hardcoded `APP_SECRET` in `.env` (not env-substituted) → `static-key-leak`
- Custom user provider that authenticates without password check → `incorrect-authorization`
