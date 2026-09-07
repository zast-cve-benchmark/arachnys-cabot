---
name: global-audit-config
description: Project-wide audit of configuration files and framework-default settings. Foundation-layer skill always dispatched by global-audit. Covers hardcoded secrets in config (DB passwords / API tokens / cloud creds), insecure framework defaults (Actuator exposure, debug=true, CORS *), missing security headers, TLS misconfig.
---

# global-audit-config

You audit the project's configuration surface: what's set in config files, what framework defaults are left on, what dangerous toggles are enabled. Framework-agnostic in the umbrella sense — the specifics vary by stack.

## Scope

In scope (this skill):
- Config files: `.yml`, `.yaml`, `.properties`, `.env*`, `application.*`, `settings.py`, `config.py`, `config/*.php`, `wp-config.php`, etc.
- Framework default settings left on: Spring Boot Actuator exposure, Django `DEBUG=True`, Flask `DEBUG=True`, Express `x-powered-by`, Nginx default error pages, etc.
- CORS: wildcard `Access-Control-Allow-Origin: *` (especially with credentials)
- TLS / HTTPS: default cipher suites, missing HSTS, mixed-content
- Hardcoded DB passwords / API tokens / cloud credentials in source or config

Out of scope:
- AES/HMAC keys / salts → `global-audit-crypto`
- JWT signing keys / OAuth secrets → `global-audit-auth`
- Per-endpoint security headers (set in controller) → `audit-endpoint`

## Scan locations

### Config files (read these first, regardless of language)
```
find <project-root> -maxdepth 5 \
  -name "*.yml" -o -name "*.yaml" -o -name "*.properties" \
  -o -name ".env*" -o -name "settings.py" -o -name "config.py" \
  -o -name "*.toml" -o -name "config.json" \
  -not -path "*/node_modules/*" -not -path "*/.git/*"
```

Open each and look for:
- Hardcoded strings in keys/values containing `password`, `secret`, `token`, `key`, `apikey`, `dsn`
- Framework feature toggles set to dangerous values
- CORS / security header config

### Spring Boot specific
- `application.yml` / `application.properties`
- `management.endpoints.web.exposure.include=*` → Actuator endpoints all exposed
- `management.endpoint.shutdown.enabled=true` → remote shutdown endpoint
- `spring.h2.console.enabled=true` (production) → H2 web console
- `debug=true` / `trace=true`
- `server.error.include-stacktrace=ALWAYS`

### Exposed admin / monitor consoles & config-dump endpoints (any framework)
A built-in management/monitor UI or a "dump my config/state" endpoint reachable
without auth leaks DB DSNs, credentials, internal topology. Grep + check the
auth gate:
- **Druid monitor console**: `DruidStatViewServlet`, a `/druid/*` servlet/route,
  `spring.datasource.druid.stat-view-servlet.enabled=true` — and whether
  `login-username`/`allow` are set. Unauthed `/druid/index.html` exposes SQL,
  sessions, datasource URLs → `information-disclosure`.
- **DB web consoles**: H2 (`/h2-console`), Adminer, phpMyAdmin, **Apache Derby /
  network maintenance ops endpoints** (e.g. a `…/ops/derby` route that runs SQL)
  reachable unauthenticated → `information-disclosure`.
- **Config / state dump endpoints**: any handler that returns the running
  configuration, env, or datasource details (paths like `…/config/dump`,
  `…/actuator/env`, `…/debug/…`, `…/dump`). If it echoes jdbcUrl / datasource /
  secrets without auth → `information-disclosure`.

### Database seed / init scripts — default & hardcoded credentials
Seeded credentials are a real, commonly-missed exposure (a shipped default admin
account anyone can log in as). Scan SQL fixtures and data-init scripts, not just
config:
```
find <project-root> -maxdepth 6 \( -name "*.sql" -o -name "data.sql" \
  -o -name "import.sql" -o -name "schema*.sql" -o -name "*seed*" -o -name "*init*.sql" \) \
  -not -path "*/node_modules/*"
```
Look for `INSERT INTO <users-table> ... VALUES (..., 'admin', '<password-or-hash>', ...)`
and ORM seed fixtures. A seeded super-admin with a default/guessable password
(`admin/admin123`, `root/root`), or a hash of one, that ships enabled in
production → `weak-credentials`. Note the account + where it's seeded.

### Django
- `settings.py`
- `DEBUG = True` (in production settings)
- `ALLOWED_HOSTS = ['*']`
- `SECRET_KEY = 'literal-string'` (must come from env)
- `SECURE_HSTS_SECONDS = 0` (HSTS disabled)
- Missing `SECURE_BROWSER_XSS_FILTER`, `SECURE_CONTENT_TYPE_NOSNIFF`, etc.

### Flask / FastAPI
- `app.config['DEBUG'] = True` in production
- `app.run(debug=True, host='0.0.0.0')`

### Node / Express
- `app.use(cors())` without origin allowlist → wildcard
- `app.disable('x-powered-by')` MISSING → fingerprinting
- `helmet()` middleware missing

### Go (when CODE_LANGUAGE=go)
- `http.ListenAndServe` without TLS for sensitive endpoints
- `html/template` autoescape relied on but template syntax bypasses (e.g., `template.HTML(...)`)
- `tls.Config` with `InsecureSkipVerify: true`
- `tls.Config` with weak `MinVersion` (< TLS 1.2)

### PHP
- `phpinfo()` reachable in production
- `display_errors = On`
- `expose_php = On`

## Config secrets — judgment

Trust boundary judgment (apply to any hardcoded secret in config):
- Who SHOULD know this secret? Who can ACTUALLY obtain it?
- Open-source / self-hosted: default secret is a vuln if users typically don't rotate it (default DB password, default Redis password)
- Enterprise internal: any hardcoded secret is a vuln (should be env var / Kubernetes secret / vault)
- If users are forced to set it at deploy time (no working default), it's not a vuln

Grep heuristics:
```
grep -rn "password\s*[:=]\s*['\"]" <project-root>/config <project-root>/src/main/resources
grep -rn "token\s*[:=]\s*['\"]\|secret\s*[:=]\s*['\"]" <project-root>/config
grep -rn "AKIA[0-9A-Z]\{16\}" <project-root>          # AWS access key id
grep -rn "AIza[0-9A-Za-z_-]\{35\}" <project-root>     # Google API key
grep -rn "ghp_[0-9A-Za-z]\{36\}\|github_pat_" <project-root>  # GitHub tokens
```

## Output

| Pattern | category_id |
|---|---|
| Spring Actuator endpoints all exposed; `debug=true`; `display_errors=On` etc. | `information-disclosure` |
| `ALLOWED_HOSTS=['*']` or equivalent | `information-disclosure` |
| CORS `Access-Control-Allow-Origin: *` (especially with credentials) | `cors-misconfiguration` |
| TLS `InsecureSkipVerify: true` / weak MinVersion | `insecure-crypto-configuration` |
| Missing security headers (HSTS, CSP, X-Frame-Options) when otherwise hardened | `business-logic-flaw` |
| DB password / API token / cloud credential hardcoded in config with leakable scope | `static-key-leak` |
| H2 console / Adminer / phpMyAdmin reachable | `information-disclosure` |
| Druid monitor console / Derby maintenance ops / unauthed config-dump endpoint exposing jdbcUrl/datasource | `information-disclosure` |
| Default / seeded credentials in SQL init or data scripts (`admin/admin123` etc.) shipped enabled | `weak-credentials` |
| Default or hardcoded login password in config (e.g. `admin.password=admin123` in `application.yml`) | `weak-credentials` |

## Anti-Hallucination Rules

- ✗ Do NOT report a default value as vuln without checking it's actually used in production
- ✗ Do NOT report missing `Secure` cookie flag for a localhost-only dev config
- ✗ Do NOT guess at framework defaults — Read the actual config file

- ✓ MUST Read the config file before claiming a setting
- ✓ MUST distinguish dev vs prod configurations (look at filename / profile)

Core principle: **Better to miss than to false-positive.**

## Output format

Write findings as a flat JSON array `[ {...}, ... ]` of `SimpleVulnInfo`. See `record-vulnerabilities` for the schema and the mandatory `validate_vulns.py` step. Empty findings → write `[]` (still valid).

No per-endpoint issues — focus on GLOBAL / project-wide defects only.
