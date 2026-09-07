# Login / Authentication Business Logic Analysis Guide

Module-specific guidance for the **Login Agent** during Step 1.
Read this alongside `@agents/BUSINESS_ANALYZER.md` which defines the universal framework.

---

## Scope Definition (范围定义)

> **IMPORTANT**: The "Login" module covers ALL authentication and authorization mechanisms,
> not just traditional login forms. This includes:
>
> - **User Authentication**: Login forms, API authentication, credential verification
> - **Token-Based Auth**: JWT, Bearer tokens, API keys, OAuth tokens
> - **Session Management**: Cookie-based sessions, session stores
> - **SSO/Federation**: OAuth 2.0, OIDC, SAML, external identity providers
> - **Access Control**: Authorization middleware, permission checks, role validation
> - **Proxy Authentication**: Auth proxies (like vmauth), gateway authentication
>
> If the project has NO traditional login form but HAS authentication mechanisms
> (e.g., JWT validation, API key verification, bearer token checks), analyze those.

---

## Objective

Analyze the project's **authentication/authorization** implementation end-to-end.
Understand the developer's original design intent, trace every execution path,
and capture the complete workflow into `business_logic.json`.

> Goal: Build a precise mental model of how authentication works in this codebase,
> so Step 2 can detect logic flaws against it.
>
> 目标: 完整理解认证授权的实现逻辑，为后续 SINK 检测提供准确的代码上下文。

---

## 1. Entry Point Discovery (入口识别)

Locate all authentication-related routes, handlers, and middleware.
Search using language-specific patterns:

### Authentication Entry Points to Find

1. **Traditional Login Endpoints**: `/login`, `/signin`, `/auth`
2. **Token Endpoints**: `/token`, `/oauth/token`, `/refresh`
3. **Callback Endpoints**: `/callback`, `/oauth/callback`, `/auth/callback`
4. **API Auth Headers**: `Authorization: Bearer`, `X-API-Key`, custom auth headers
5. **Auth Middleware/Filters**: Code that intercepts requests to validate credentials
6. **Auth Configuration**: Config files defining users, tokens, keys, or auth rules

### Java (Spring Boot / Spring MVC / Shiro)
```
Keywords:  login, authenticate, signIn, doLogin, auth, token, jwt, bearer, authorize
Routes:    @PostMapping("/login"), @RequestMapping("/auth"), @GetMapping("/oauth/callback")
Config:    SecurityConfig, WebSecurityConfigurerAdapter, ShiroConfig, JwtConfig
Filters:   UsernamePasswordAuthenticationFilter, JwtAuthFilter, BearerTokenFilter
Classes:   AuthController, TokenService, JwtTokenProvider, AuthorizationFilter
```

### PHP (Laravel / ThinkPHP)
```
Keywords:  login, authenticate, attempt, doLogin, jwt, token, bearer, guard
Routes:    Route::post('/login'), Route::post('/oauth/token'), $router->middleware('auth')
Config:    config/auth.php, config/jwt.php, middleware/Authenticate.php
Guards:    Auth::attempt(), Auth::guard(), JWTAuth::attempt(), JWTAuth::parseToken()
Classes:   AuthController, TokenController, JWTMiddleware, AuthenticatesUsers
```

### Python (Django / Flask / FastAPI)
```
Keywords:  login, authenticate, login_view, LoginView, jwt, token, bearer, oauth
Routes:    path('login/', ...), @app.route('/login'), @router.post('/token')
Config:    settings.AUTHENTICATION_BACKENDS, settings.REST_FRAMEWORK, JWT_AUTH
Decorators: @login_required, @permission_required, @jwt_required, Depends(oauth2_scheme)
Classes:   TokenObtainPairView, JWTAuthentication, OAuth2PasswordBearer
```

### Go (Gin / Echo / Fiber / net/http)
```
Keywords:  Login, HandleLogin, AuthHandler, SignIn, Auth, JWT, Token, Bearer, Verify
Routes:    r.POST("/login", ...), e.POST("/auth", ...), http.HandleFunc("/token", ...)
Config:    JWT config structs, auth middleware setup, auth_config.yaml
Middleware: authMiddleware, JWTMiddleware, BearerAuthMiddleware, VerifyToken
Files:     *auth*.go, *jwt*.go, *token*.go, *session*.go, auth_config.go
Classes:   AuthConfig, JWTConfig, UserInfo, TokenVerifier, VerifierPool, Claims
```

### Node.js (Express / Koa / NestJS)
```
Keywords:  login, authenticate, signIn, passport, jwt, token, bearer, oauth
Routes:    app.post('/login', ...), router.post('/auth/login'), @Post('token')
Config:    passport.use(new LocalStrategy(...)), passport.use(new JwtStrategy(...))
Middleware: passport.authenticate('jwt'), jwt.verify(), bearerToken()
Classes:   AuthController, AuthService, JwtStrategy, TokenService, AuthGuard
```

---

## 2. Execution Flow Tracing (执行流追踪)

For each login workflow discovered, trace through the 5 layers defined in
BUSINESS_ANALYZER.md. Pay special attention to these **login-critical** aspects:

### Pre-Processing Layer
- CAPTCHA / verification code validation (if present)
- Input sanitization on username and password fields
- Request rate limiting or anti-brute-force middleware
- Parameter decryption (some apps encrypt credentials client-side)

### Auth Layer
- **Credential lookup**: how is the user record fetched? (by username? email? phone? config file? database?)
- **Password verification**: what algorithm? (bcrypt, argon2, md5, sha256+salt?)
- **Token verification**: how are JWT/bearer tokens validated? (signature, claims, expiration)
- **API key verification**: how are API keys validated? (database lookup, config comparison)
- **Config-based auth**: are users defined in config files (YAML, JSON)? How are credentials matched?
- **Multi-factor**: is 2FA/MFA/OTP checked? At what stage?
- **SSO/OAuth/OIDC**: external identity provider flows, callback handling, token exchange
- **Skip/bypass options**: are there config options to skip verification? (e.g., `skip_verify`, `insecure`)

### Business Logic Layer
- Account status checks: locked? disabled? pending verification?
- Login failure counting and lockout logic
- Session/token generation after successful auth
- "Remember me" implementation
- Login event logging and notification

### Response Layer
- What error messages are returned for invalid username vs. invalid password?
- Are credentials or tokens included in the HTTP response?
- Is session ID rotated after successful authentication?
- Response headers: Set-Cookie attributes (HttpOnly, Secure, SameSite)

### Async Layer (if exists)
- Post-login event dispatching (login notification emails, audit log writes)
- Session synchronization across distributed nodes

---

## 3. Global Components to Capture (全局组件)

Record **every** middleware/filter/interceptor that touches the login flow:

| Priority | Component Type | What to Record |
|----------|---------------|----------------|
| HIGH | Auth filters (JWT filter, session filter) | Order in chain, bypass conditions |
| HIGH | Rate limiter / brute-force protector | Thresholds, scope (IP/user/global) |
| HIGH | CSRF protection middleware | Is login endpoint exempt? Why? |
| MEDIUM | Logging / audit middleware | What login events are logged? |
| MEDIUM | CORS configuration | Allowed origins for login endpoint |
| LOW | Request body parsers | Size limits, content-type handling |

---

## 4. Configuration Extraction (配置提取)

Capture these login-relevant config items:

- **Session/Token config**: expiration time, token type (JWT/opaque), signing algorithm, secret key source
- **Password policy**: minimum length, complexity requirements, hashing algorithm
- **Lockout policy**: max attempts, lockout duration, scope (per-user, per-IP)
- **CAPTCHA config**: provider, trigger conditions, validation endpoint
- **OAuth/SSO config**: client ID, redirect URIs, allowed providers, PKCE settings
- **Security headers**: HSTS, CSP, X-Frame-Options on login pages

---

## 5. Code Snippet Extraction Rules (代码提取规则)

- Include 3-5 lines of context above and below each key code block
- Keep complete `if-else` branches and `try-catch` blocks -- do not truncate
- If a snippet exceeds 50 lines, extract the core logic and note `[truncated]`
- Always record accurate `file_path` and `line_range`
- Preserve original comments -- they reveal developer intent

---

## Output

Write to `{output_dir}/login/business_logic.json`.

Schema: see `@reference/JSON_SCHEMAS.md` section: business_logic.

Use `workflow_id` prefix `login_` (e.g., `login_001`, `login_002`).

Each distinct login pathway (standard login, OAuth callback, SSO redirect,
API token auth, mobile login) should be a separate workflow entry.

---

## Checklist Before Completing Step 1

- [ ] All login API endpoints identified
- [ ] Complete filter/middleware chain documented with execution order
- [ ] Password verification logic fully traced (algorithm + salt handling)
- [ ] Session/token generation logic captured
- [ ] Error response messages recorded verbatim
- [ ] Lockout/rate-limit mechanism documented (or noted as absent)
- [ ] CAPTCHA flow documented (or noted as absent)
- [ ] OAuth/SSO flow documented if present
- [ ] All config values captured with file paths
- [ ] JSON output is well-formed with non-empty `workflows[]`

> Proceed to Step 2 only after this checklist is complete.
