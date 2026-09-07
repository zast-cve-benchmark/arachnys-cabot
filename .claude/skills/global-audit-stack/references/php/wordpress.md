# WordPress Configuration Audit Reference

Used by audit-stack when LANGUAGE=php, FRAMEWORK=wordpress. Covers WordPress's cookie-based authentication architecture, wp-config.php security key handling, debug mode, file editing controls, capability checks, nonce verification, and credential storage.

## Architecture: Cookie-Based Authentication

WordPress authenticates users via cookies (`wordpress_logged_in_*`). After login, WordPress sets several cookies signed with security keys defined in `wp-config.php`. Nonces are used for CSRF protection in admin pages and AJAX handlers.

Key points to trace:
- **Security keys** in `wp-config.php`: `AUTH_KEY`, `SECURE_AUTH_KEY`, `LOGGED_IN_KEY`, `NONCE_KEY` (and their `_SALT` variants). These are used for cookie hashing. If they are set to known sample values, empty strings, or identical across installations, cookie forgery is possible.
- **`is_admin()` vs capability checks** — `is_admin()` only checks if the current request is for an admin URL, not whether the current user is an administrator. Code that uses `is_admin()` as an authorization gate is incorrect; `current_user_can()` is the right check.
- **`wp_authenticate_user` filter** — plugins can hook into the authentication process. A filter that returns a `WP_User` unconditionally or ignores the password bypasses WordPress's own verification.
- Cookie auth tokens are generated using the security keys as HMAC secrets. Predictable or reused keys make cookie forgery feasible.

## wp-config.php Configuration Security

`wp-config.php` is the single source of truth for WordPress credentials and feature flags.

Key points to trace:
- `DISALLOW_FILE_EDIT` — if not defined or set to `false`, administrators can edit theme and plugin PHP files directly from the WordPress admin panel, enabling arbitrary code execution.
- `WP_DEBUG` — if `true` in production, PHP errors, notices, and warnings are displayed in browser output, disclosing internal paths and stack traces.
- `WP_DEBUG_DISPLAY` — if `true` (the default when `WP_DEBUG` is on), errors are displayed inline rather than written to a log file.
- `FORCE_SSL_ADMIN` — if not set or `false`, admin session cookies are transmitted over HTTP.
- `DB_PASSWORD` stored as a plaintext literal in `wp-config.php` committed to version control exposes database credentials.

## Nonce Verification (CSRF)

WordPress uses nonces for CSRF protection in admin pages and AJAX handlers.

Key points to trace:
- AJAX handlers registered via `wp_ajax_` or `wp_ajax_nopriv_` hooks — do they call `check_ajax_referer()` or `wp_verify_nonce()` before performing state-changing operations?
- Admin form handlers — do they call `check_admin_referer()` before processing POST data?
- Absence of nonce checks in custom plugin AJAX endpoints handling sensitive operations (user role changes, option updates, file uploads).

## Custom Authentication Plugins

Plugins that override authentication (SSO integrations, magic-link login, social login) hook into `wp_authenticate`, `authenticate`, or `wp_authenticate_user`.

Key points to trace:
- Does the plugin authenticate the user by trusting a parameter (email, user ID, token) without cryptographic verification of a server-issued credential?
- Does the plugin short-circuit the password check by returning a `WP_User` object before WordPress performs `wp_check_password()`?

## Output

- `wp-config.php` `AUTH_KEY` / `SECURE_AUTH_KEY` / `LOGGED_IN_KEY` / `NONCE_KEY` (and `*_SALT` variants) using known sample values or empty strings → `static-key-leak`
- `define('WP_DEBUG', true)` reachable in prod, or `WP_DEBUG_DISPLAY` true → `information-disclosure`
- `define('DISALLOW_FILE_EDIT', false)` (or unset) allowing in-admin theme/plugin file editing → `incorrect-authorization`
- Custom auth plugin / `wp_authenticate_user` filter that bypasses password check → `incorrect-authorization`
- Cookie auth tokens generated via predictable seed (e.g., user id + constant secret) → `static-key-leak`
- `wp-config.php` `DB_PASSWORD` plaintext + version-controlled → `static-key-leak`
- `is_admin()` used as sole authorization gate instead of `current_user_can()` → `incorrect-authorization`
- `wp_ajax_` / `wp_ajax_nopriv_` handler missing `check_ajax_referer()` or `wp_verify_nonce()` → `csrf`
