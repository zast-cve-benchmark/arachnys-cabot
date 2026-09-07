# Spring Security Configuration Audit Reference

Used by audit-stack when LANGUAGE=java, FRAMEWORK=spring-security. Covers Spring Security's filter chain configuration, CORS, session, rememberMe, JWT decoder, and CSRF setup.

## Architecture: Filter Chain

Spring Security implements a `SecurityFilterChain` — an ordered list of `Filter` instances that process every HTTP request before it reaches the controller. Each filter has one job: authentication, authorization, CSRF, CORS, session management, etc.

The request flows through filters in order. If any filter rejects the request, the response is returned immediately. The controller is never reached.

Key points to trace:
- **Filter ordering** — which filter runs first? If a business filter or controller mapping runs before the auth filter, requests bypass authentication.
- **`SecurityFilterChain` bean** — which URL patterns does it cover? Are there paths that fall outside?
- **`@PreAuthorize` / `@Secured`** — method-level annotations add authorization on top of URL-level rules. Trace which methods have them and which don't.
- **CSRF** — enabled by default. `csrf().disable()` explicitly turns it off. Understand why it was disabled and whether the reason is valid.

## CORS Configuration

CORS in Spring is configured at two levels:
- **Global**: `CorsConfigurationSource` bean or `WebMvcConfigurer.addCorsMappings()`
- **Per-controller**: `@CrossOrigin` annotation

When a browser makes a cross-origin request, it sends an `Origin` header. The server decides whether to allow it based on `allowedOrigins`. The `allowCredentials` flag controls whether cookies are included.

Key points to trace:
- What origins are allowed? Where is the `Origin` header value obtained from?
- Is `allowCredentials` set? If so, are the allowed origins sufficiently restrictive?
- If both global and per-controller CORS configs exist, which one takes effect? Do they conflict?

## Session Management

Spring Security's `SessionManagementFilter` controls session behavior:
- `maximumSessions()` — limits concurrent sessions per user
- `sessionFixation()` — controls session ID rotation (migrateSession, newSession, none)
- `sessionCreationPolicy()` — STATELESS, IF_REQUIRED, ALWAYS, NEVER

Key points to trace:
- What is the session creation policy? If STATELESS, where is authentication state stored?
- Is session fixation protection enabled? What happens at login — does the session ID change?

## JWT (Spring Security OAuth2 Resource Server)

Spring Security's JWT support lives in `spring-security-oauth2-jose` and
`spring-security-oauth2-resource-server`. Key configuration points:

- **Decoder construction**: `NimbusJwtDecoder.withJwkSetUri(...)` or
  `.withPublicKey(...)` or `.withSecretKey(...)`. The decoder shape
  determines what `alg` headers are accepted.
- **Issuer-based config**: `JwtDecoders.fromIssuerLocation(uri)` /
  `fromOidcIssuerLocation(uri)` auto-discovers JWKS. Verify the issuer
  URI points to a trusted authorization server.
- **Algorithm enforcement**: A `NimbusJwtDecoder` constructed with
  `.withJwkSetUri` accepts whatever algorithms the JWKS advertises.
  Construct with explicit `jwsAlgorithm(SignatureAlgorithm.RS256)` to
  pin the algorithm.
- **Validator chain**: Inspect `setJwtValidator(...)`. Default is
  `JwtTimestampValidator + JwtIssuerValidator`. Custom validators must
  not bypass timestamp checks.
- **Resource server config**: `http.oauth2ResourceServer().jwt()` is
  the common entrypoint; absent this, JWT auth is not enforced even if
  a decoder bean exists.

For cross-language JWT misuse patterns (decode-vs-verify, alg=none,
weak key), see `global-audit-auth/SKILL.md` (JWT section).

## rememberMe (TokenBasedRememberMeServices)

Spring Security's rememberMe feature signs a cookie containing
`username:expirationTime:md5Hex(username:expirationTime:password:key)`.
The signing key comes from `.rememberMe().key(<KEY>)`.

- **Key source**: A `.rememberMe().key(<KEY>)` call accepting a
  hardcoded string literal is a `static-key-leak` — every deployment
  using the same source code can mint each other's rememberMe cookies.
- **Key omission**: If `.rememberMe().key(...)` is NOT called,
  Spring Security generates a random key at startup. This is per-process,
  so the cookies do not survive a restart (acceptable in single-node
  deployments, broken in multi-node without sticky sessions).
- **Token services swap**: `.tokenRepository(...)` switches from MD5-
  signed cookie to a database-backed `PersistentTokenRepository`.
  Check that the underlying table has tight access controls.
- **Cookie attributes**: rememberMe cookie defaults inherit from the
  servlet container — verify `Secure` and `HttpOnly` flags via the
  remembered cookie name (default `remember-me`).

## Output

- Misconfigured filter chain (overly permissive `permitAll`, missing roles on sensitive paths) → `incorrect-authorization`
- `csrf().disable()` on POST endpoints without an alternative origin check → `csrf`
- Hardcoded `rememberMe().key(...)` string literal → `static-key-leak`
- `cors().configurationSource(...)` returning `*` origin with credentials → `cors-misconfiguration`
- JWT decoder accepting `alg=none` or missing algorithm whitelist → `incorrect-signature-verification`
- Default `HttpSession` config without timeout or `Secure` cookie attrs → `business-logic-flaw`
- `sessionFixation().none()` or session-fixation protection explicitly disabled → `incorrect-authorization`
