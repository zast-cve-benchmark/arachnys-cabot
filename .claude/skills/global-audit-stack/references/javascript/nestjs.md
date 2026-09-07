# NestJS Configuration Audit Reference

Used by audit-stack when LANGUAGE=javascript, FRAMEWORK=nestjs. Covers guard-based authorization, global APP_GUARD registration, JWT module configuration, exception filter behavior, CORS setup, and input validation via ValidationPipe.

## Architecture: Guards

NestJS uses guards for authorization: `@UseGuards(AuthGuard('jwt'))`. Guards can be applied per-route, per-controller, or globally.

Key points to trace:
- **Global guards** — registered via `APP_GUARD` provider in the root module. If a global auth guard is registered, all routes require auth unless individually marked with a `@Public()` decorator (or equivalent). Check which routes are marked public and whether any sensitive operations are included.
- **Per-route / per-controller guards** — routes and controllers without a guard have no authentication enforcement. Enumerate controllers that handle sensitive operations and confirm a guard is applied.
- **Guard return value** — a guard must return `true` (or a `Promise<true>` / `Observable<true>`) to allow access. A custom guard that catches its own errors and returns `true` as a fallback effectively becomes a pass-through.

## JWT Module Configuration

`JwtModule.register({ secret, signOptions })` or `JwtModule.registerAsync({ useFactory: ... })` configures the JWT secret and signing options for the whole module.

Key points to trace:
- Is `secret` a string literal in the module decorator, or is it loaded from `ConfigService` / `process.env`?
- Is `signOptions.expiresIn` set? If omitted, tokens do not expire.
- When `JwtModule.registerAsync` is used, does the factory function read from a secrets manager or fall back to a hardcoded default?

For cross-language JWT misuse patterns (decode vs verify, alg=none), see `global-audit-auth/SKILL.md (JWT section)`.

## Exception Filters

NestJS exception filters handle thrown exceptions and shape the HTTP response. `@Catch()` without arguments catches all exceptions globally. The intended behavior is to return structured error responses without exposing internal details.

Key points to trace:
- Does the exception filter include `exception.message` or `exception.stack` in the response body? Stack traces disclose internal paths, dependency versions, and application logic.
- Is user input reflected in an error message that is then rendered in an HTML context? This is a potential XSS vector if the response type is `text/html`.
- Is a global exception filter registered that swallows errors silently, masking auth failures?

## CORS Configuration

NestJS exposes CORS via `app.enableCors(options)` in `main.ts`.

Key points to trace:
- Is `enableCors({ origin: '*', credentials: true })` configured? The wildcard origin combined with credentials is a misconfiguration — it allows any origin to make credentialed cross-origin requests.
- Dynamic `origin` callbacks that reflect the request `Origin` without validation are equivalent to a wildcard.
- Is CORS configured only in the NestJS app, or also at a reverse-proxy layer? Conflicting configurations can create bypass opportunities.

## Input Validation: ValidationPipe

`ValidationPipe` with `class-validator` DTOs enforces input shape and type constraints. If not registered globally, individual controllers or routes that omit `@UsePipes(ValidationPipe)` receive unvalidated input.

Key points to trace:
- Is `app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true }))` called in `main.ts`?
- Is `whitelist: true` set? Without it, extra properties on the request body are passed through to the handler even if not declared in the DTO.
- Are there controller methods that accept a raw `body` parameter (bypassing DTOs entirely) on sensitive operations?

## Output

- `@UseGuards()` missing from controllers or routes that handle auth-protected operations → `incorrect-authorization`
- Global `APP_GUARD` not registered, leaving all routes public by default → `incorrect-authorization`
- `JwtModule.register({ secret: '<HARDCODED>' })` literal secret in module decorator → `static-key-leak`
- Custom exception filter that includes `exception.stack` or internal details in the response body in prod → `information-disclosure`
- `app.enableCors({ origin: '*', credentials: true })` wildcard + credentials combo → `cors-misconfiguration`
- `ValidationPipe` not registered globally, allowing unvalidated or extra-property DTOs into sensitive handlers → `business-logic-flaw`
