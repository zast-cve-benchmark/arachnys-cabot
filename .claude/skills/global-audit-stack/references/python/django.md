# Django Configuration Audit Reference

Used by audit-stack when LANGUAGE=python, FRAMEWORK=django. Covers Django's middleware ordering, SECRET_KEY handling, ALLOWED_HOSTS, CORS configuration, CSRF protection, authentication backends, DRF permissions, session cookie security, and template rendering.

## Architecture: Authentication Pipeline

Django's authentication is built around `django.contrib.auth`. The `AuthenticationMiddleware` adds the authenticated user to every request as `request.user`. Views are protected using `@login_required`, `LoginRequiredMixin`, or DRF's `permission_classes`.

The middleware runs in `MIDDLEWARE` order. `request.user` is set by `AuthenticationMiddleware` — any code that runs before it sees `AnonymousUser`.

Key points to trace:
- **MIDDLEWARE order** — `AuthenticationMiddleware` must appear before any middleware that reads `request.user`. If it's missing or ordered wrong, `request.user` is `AnonymousUser` everywhere.
- **SECRET_KEY** — used for session signing, CSRF tokens, password reset tokens, and flash messages. Where is it defined? Is it loaded from an environment variable or secrets manager, or is a string literal hardcoded in `settings.py`?
- **Session engine** — `SESSION_ENGINE` determines where session data is stored (database, cache, signed cookies, files). Signed-cookie sessions store all data in the browser — integrity is guaranteed by `SECRET_KEY`, but the data is visible to the user.
- **Custom authentication backends** — `AUTHENTICATION_BACKENDS` defines how users are authenticated. Custom backends may implement weaker validation than the default `ModelBackend` (e.g., skipping password verification).

## Settings: DEBUG and ALLOWED_HOSTS

`DEBUG=True` activates the interactive exception debugger, which exposes full tracebacks, local variable values, and installed settings to the browser. In production this is an information disclosure vulnerability.

`ALLOWED_HOSTS` is the list of hostnames the application will accept `Host:` headers for. An empty list (`[]`) disables host-header validation when `DEBUG=True`. Setting it to `["*"]` disables validation unconditionally.

Key points to trace:
- Is `DEBUG` conditionally set from an environment variable, or unconditionally `True` in the deployed settings file?
- Is `ALLOWED_HOSTS` set to `["*"]` or empty in the production settings module?

## DRF (Django REST Framework) Permission Model

DRF separates authentication (who are you?) from permissions (can you do this?):
- **Authentication classes** — identify the user (`TokenAuthentication`, `JWTAuthentication`, `SessionAuthentication`)
- **Permission classes** — check access (`IsAuthenticated`, `IsAdminUser`, custom permissions)
- **`DEFAULT_PERMISSION_CLASSES`** — the global default applied to all views that do not declare their own `permission_classes`

Key points to trace:
- What is `REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']`? If it is `AllowAny` or empty, every view that omits an explicit `permission_classes` is publicly accessible by default.
- Token authentication — do tokens expire? If not, stolen tokens are valid indefinitely.

## CORS Configuration (django-cors-headers)

`django-cors-headers` adds `CorsMiddleware` to `MIDDLEWARE`. The key settings:
- `CORS_ALLOWED_ORIGINS` / `CORS_ORIGIN_WHITELIST` — explicit list of allowed origins
- `CORS_ALLOW_ALL_ORIGINS` — if `True`, reflects every `Origin` header unconditionally
- `CORS_ALLOW_CREDENTIALS` — if `True`, the browser will include cookies in cross-origin requests

Key points to trace:
- Is `CORS_ALLOW_ALL_ORIGINS=True` combined with `CORS_ALLOW_CREDENTIALS=True`? This allows any origin to make credentialed cross-origin requests.
- Is `CorsMiddleware` placed before `CommonMiddleware` in `MIDDLEWARE`? Incorrect ordering can cause preflight requests to be rejected before CORS headers are added.

## CSRF Protection

Django's `CsrfViewMiddleware` generates a CSRF token, stores it in a cookie, and validates it on every POST/PUT/PATCH/DELETE request. Forms include the token via `{% csrf_token %}`; AJAX sends it in the `X-CSRFToken` header.

Key points to trace:
- Is `django.middleware.csrf.CsrfViewMiddleware` present in `MIDDLEWARE`? If removed, all state-changing requests are unprotected.
- `@csrf_exempt` applied at the class level or to a whole module rather than to a specific view — how many state-changing operations does it expose?
- `CSRF_COOKIE_HTTPONLY` — if `False`, JavaScript can read the CSRF cookie (needed for AJAX, but increases XSS impact).

## Session Cookie Security

Django sets session cookie attributes via settings:
- `SESSION_COOKIE_SECURE` — if `False`, the session cookie is transmitted over HTTP
- `SESSION_COOKIE_HTTPONLY` — if `False`, JavaScript can read the session cookie
- `SESSION_COOKIE_SAMESITE` — `'Strict'` or `'Lax'` prevents cross-site cookie submission; `None` (or missing) offers no protection

Key points to trace:
- Are `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, and `SESSION_COOKIE_SAMESITE` all set in the production settings file?
- Is `SESSION_COOKIE_AGE` set to a reasonable duration, or is it left at the default (2 weeks)?

## Template Rendering

Django templates auto-escape HTML by default. `{{ variable }}` escapes `<`, `>`, `&`, `"`, `'` before rendering.

Key points to trace:
- `|safe` filter or `{% autoescape off %}` — disables escaping. If user input flows through these, the output is raw HTML.
- `render_to_string()` or string concatenation in templates — bypasses the template engine's auto-escaping.

## Output

- `DEBUG=True` in production settings → `information-disclosure`
- `SECRET_KEY` hardcoded in `settings.py` (not loaded from env/secrets manager) → `static-key-leak`
- `ALLOWED_HOSTS` empty or `["*"]` → `business-logic-flaw`
- `CORS_ALLOW_ALL_ORIGINS=True` combined with `CORS_ALLOW_CREDENTIALS=True` (django-cors-headers) → `cors-misconfiguration`
- CSRF middleware (`django.middleware.csrf.CsrfViewMiddleware`) removed from `MIDDLEWARE` → `csrf`
- `@csrf_exempt` applied broadly (whole module / class) rather than per-view → `csrf`
- Custom auth backend in `AUTHENTICATION_BACKENDS` that does not validate password → `incorrect-authorization`
- DRF permission classes `AllowAny` set globally in `REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']` → `incorrect-authorization`
- `SESSION_COOKIE_SECURE=False` / `SESSION_COOKIE_HTTPONLY=False` / missing `SESSION_COOKIE_SAMESITE` in prod → `business-logic-flaw`
- `|safe` filter or `{% autoescape off %}` applied to user-controlled template variables → `xss`
