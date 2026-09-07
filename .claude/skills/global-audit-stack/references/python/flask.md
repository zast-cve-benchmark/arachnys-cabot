# Flask Configuration Audit Reference

Used by audit-stack when LANGUAGE=python, FRAMEWORK=flask. Covers Flask's SECRET_KEY handling, debug mode, Flask-WTF CSRF protection, Flask-CORS configuration, session cookie security, Flask-Login enforcement, JWT decode configuration, and template rendering.

## Architecture: Session Security

Flask is a micro-framework — authentication is not built in. It is typically added via Flask-Login, Flask-JWT-Extended, or custom implementations.

Flask stores all session data in a signed cookie (via `itsdangerous`). The cookie is base64-encoded (not encrypted), then signed with `SECRET_KEY` to prevent tampering.

Key points to trace:
- **`app.secret_key` / `app.config['SECRET_KEY']`** — where is it defined? If it is a hardcoded string literal in the source, anyone with the source can forge session cookies. If it is not set at all, Flask generates a random one on startup — sessions are lost on restart and cannot be shared across workers.
- **Session visibility** — the user can base64-decode the cookie and see all session data. Sensitive values like roles or permissions stored in the session are visible to the user even without a key.
- **Flask-Login** — `login_manager.session_protection` controls session tampering detection (`'basic'`, `'strong'`). What level is configured?

## DEBUG Mode

`app.run(debug=True)` or `app.config['DEBUG'] = True` activates the Werkzeug interactive debugger, which provides an in-browser Python REPL (PIN-protected by default, but the PIN is derivable from system attributes). It also enables the reloader and extended tracebacks.

Key points to trace:
- Is `debug=True` set unconditionally, or is it gated on an environment variable (e.g., `os.getenv('FLASK_DEBUG', 'false') == 'true'`)?
- Is `FLASK_ENV=development` set in any production deployment config (`.env`, Docker `ENV`, CI secrets)?

## CSRF Protection (Flask-WTF)

Flask does not include CSRF protection by default. The `flask_wtf.CSRFProtect` extension adds it globally. It validates the `X-CSRFToken` header or `csrf_token` form field on state-changing requests.

Key points to trace:
- Is `CSRFProtect(app)` called during application initialization?
- Is `WTF_CSRF_ENABLED` set to `False` in any settings file or test config that bleeds into production?
- Are blueprints that handle state-changing operations (`POST`, `PUT`, `DELETE`) registered before or after `CSRFProtect` is initialized?

## CORS Configuration (Flask-CORS)

`flask_cors.CORS` adds CORS headers to responses. Common patterns:
- `CORS(app)` — applies to all routes with default settings (no credentials, all origins)
- `CORS(app, resources={r"/*": {"origins": "*"}})` — wildcard origin for all routes
- `CORS(app, supports_credentials=True)` — includes credentials in cross-origin responses

Key points to trace:
- Is `origins="*"` (or `resources={r"/*": {"origins": "*"}}`) combined with `supports_credentials=True`? This is a cors-misconfiguration — the `Access-Control-Allow-Origin: *` wildcard is forbidden when credentials are included, so browsers reject it, but a custom CORS implementation or misconfigured proxy could bypass this.
- Is the `CORS` call applied at the blueprint level to sensitive blueprints, or only to public API blueprints?

## Session Cookie Security

Flask session cookie attributes are set via config keys:
- `SESSION_COOKIE_SECURE` — if `False` (default), session cookie is sent over HTTP
- `SESSION_COOKIE_HTTPONLY` — if `False`, JavaScript can read the session cookie
- `SESSION_COOKIE_SAMESITE` — `'Strict'` or `'Lax'` prevents cross-site submission; missing or `None` offers no protection

Key points to trace:
- Are `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, and `SESSION_COOKIE_SAMESITE` all set in the production config?
- Is `PERMANENT_SESSION_LIFETIME` set to a reasonable duration, or left at the default (31 days)?

## Flask-Login Enforcement

`flask_login.LoginManager` handles session-based authentication. It must be registered with the app and configured with a `login_view`. Routes are protected with the `@login_required` decorator.

Key points to trace:
- Is `login_manager.login_view` set? If not, unauthorized requests to `@login_required` routes raise an error instead of redirecting.
- Are all blueprints that contain sensitive operations decorated with `@login_required`? Blueprint-level application of the decorator is possible but uncommon — check each route individually.
- Does any blueprint register routes that shadow `@login_required` routes without requiring authentication?

## JWT Decode Configuration

Custom JWT handling (using `PyJWT` directly or `flask_jwt_extended`) may disable signature verification.

Key points to trace:
- `jwt.decode(token, options={"verify_signature": False})` — skips signature verification entirely; any token is accepted regardless of issuer or integrity.
- `jwt.decode(token, algorithms=["none"])` — accepts unsigned tokens.
- `flask_jwt_extended` config: `JWT_DECODE_ALGORITHMS` and `JWT_ALGORITHM` — if `"none"` is included, unsigned tokens are accepted.

## Template Rendering

Jinja2 auto-escapes in files with `.html`, `.htm`, `.xml`, `.xhtml` extensions. Files with other extensions (`.txt`, `.json`) are not auto-escaped.

Key points to trace:
- `render_template_string()` — if user input is included in the template string argument, it is Server-Side Template Injection (SSTI). Jinja2 templates can execute arbitrary Python code via `{{ ''.__class__.__mro__[1].__subclasses__() }}`.
- Templates with non-HTML extensions that render user-controlled content without explicit escaping.

## Output

- `app.config['SECRET_KEY']` hardcoded string literal → `static-key-leak`
- `app.config['DEBUG']=True` or `app.run(debug=True)` reachable in prod → `information-disclosure`
- `flask_wtf.CSRFProtect` not registered, or `WTF_CSRF_ENABLED=False` → `csrf`
- `flask_cors.CORS(app, resources={r"/*": {"origins": "*"}})` with `supports_credentials=True` → `cors-misconfiguration`
- Session cookie without `Secure` / `HttpOnly` / `SameSite` set via `SESSION_COOKIE_*` config → `business-logic-flaw`
- `flask_login.LoginManager` configured but `login_view` not enforced, or `@login_required` missing from sensitive blueprints → `incorrect-authorization`
- Custom JWT decoder using `jwt.decode(..., options={"verify_signature": False})` → `incorrect-signature-verification`
- `render_template_string()` called with user-controlled input in the template string argument → `ssti`
