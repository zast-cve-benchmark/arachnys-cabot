# FastAPI Configuration Audit Reference

Used by audit-stack when LANGUAGE=python, FRAMEWORK=fastapi. Covers FastAPI's dependency injection authentication model, OAuth2PasswordBearer enforcement, CORSMiddleware configuration, JWT decode configuration, hardcoded secrets, debug mode, and cookie security.

## Architecture: Dependency Injection Auth

FastAPI uses dependency injection for authentication. `Depends(get_current_user)` in a route handler causes the framework to call `get_current_user` before the handler runs. If `get_current_user` raises an `HTTPException`, the request is rejected before the handler body executes.

Key points to trace:
- **No global default** — every route must explicitly declare `Depends(get_current_user)`. Routes without it have no authentication. Enumerate all routes and check which omit a `Depends(...)` on an authentication dependency.
- **`get_current_user` implementation** — how does it validate the token? Does it verify the signature, check expiry (`exp` claim), and verify the issuer (`iss`)? Or does it only decode?
- **`OAuth2PasswordBearer`** — extracts the token from the `Authorization: Bearer` header. It does NOT validate the token — that is the sole responsibility of the `get_current_user` dependency that calls it.
- **Router-level dependencies** — `APIRouter(dependencies=[Depends(get_current_user)])` applies auth to all routes on that router. Verify that sensitive routers use this pattern and that no route on a protected router overrides it with `dependencies=[]`.

## OAuth2PasswordBearer Enforcement

`OAuth2PasswordBearer(tokenUrl="/token")` declares that the app uses bearer tokens, but it is only a security scheme descriptor in OpenAPI unless used inside a `Depends(...)`.

Key points to trace:
- Is `oauth2_scheme = OAuth2PasswordBearer(...)` instantiated but never used in a `Depends(oauth2_scheme)` or `Depends(get_current_user)` on routes that handle sensitive data?
- Are there routes that accept a `token: str = Depends(oauth2_scheme)` parameter but then ignore the token value (never call a decode/verify function)?

## CORS Configuration (CORSMiddleware)

FastAPI adds CORS support via `fastapi.middleware.cors.CORSMiddleware`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    ...
)
```

Key points to trace:
- Is `allow_origins=["*"]` combined with `allow_credentials=True`? Browsers block credentialed cross-origin responses when `Access-Control-Allow-Origin` is `*`, but misconfigured proxies or non-browser clients may not enforce this. The config itself is a cors-misconfiguration.
- Is `allow_origins` built dynamically from a config value that could be set to `["*"]` in a deployment config file?
- Is `allow_methods=["*"]` and `allow_headers=["*"]` set alongside wildcard origins?

## JWT Decode Configuration

Custom JWT handling using `PyJWT`, `python-jose`, or `authlib` may disable signature verification.

Key points to trace:
- `jwt.decode(token, options={"verify_signature": False})` — accepts any token regardless of signature; authentication is entirely bypassed.
- `jwt.decode(token, algorithms=["none"])` — accepts unsigned (alg=none) tokens.
- `jwt.decode(token, key, algorithms=["HS256", "none"])` — the `none` entry in the list allows unsigned tokens.
- `python-jose`: `jose.jwt.decode(token, key, options={"verify_aud": False, "verify_exp": False})` — disables expiry and audience validation separately.

## Hardcoded Secrets

Module-level constants used as JWT signing keys or API secrets are hardcoded into source code.

Key points to trace:
- `SECRET_KEY = "..."` or `jwt_secret = "..."` defined as a string literal at module level in `main.py`, `security.py`, `config.py`, or similar.
- `settings.secret_key` populated from a `pydantic.BaseSettings` field with a non-empty `default=` value — this means the secret has a known fallback value if the env variable is missing.
- Configuration loaded from a `.env` file that is committed to the repository.

## Debug Mode

`FastAPI(debug=True)` enables the Starlette debug exception handler, which returns full Python tracebacks (including local variable values) in HTTP responses. This is an information disclosure risk in production.

Key points to trace:
- Is `FastAPI(debug=True)` set unconditionally, or gated on `settings.debug` loaded from an environment variable?
- Is `uvicorn.run(app, ..., reload=True)` reachable in the production entry point? The `reload=True` flag implies development mode and often co-occurs with `debug=True`.

## Cookie Security

FastAPI does not set cookies by default — cookies are set via `Response.set_cookie(...)` calls in route handlers. Unlike Django/Flask, there is no global cookie config.

Key points to trace:
- `response.set_cookie(key="session", value=..., httponly=False, secure=False, samesite=None)` — each `set_cookie` call must independently set `httponly=True`, `secure=True`, and a `samesite` value.
- Authentication tokens stored in cookies (rather than `Authorization` header) — are the cookies set with `Secure` and `HttpOnly`?

## Output

- `OAuth2PasswordBearer` declared but not actually checked (no `Depends(...)` on sensitive routes) → `incorrect-authorization`
- `CORSMiddleware(allow_origins=["*"], allow_credentials=True)` → `cors-misconfiguration`
- Custom JWT decoder using `jwt.decode(token, options={"verify_signature": False})` → `incorrect-signature-verification`
- Hardcoded secret in `SECRET_KEY` / `jwt_secret` module-level constant → `static-key-leak`
- `debug=True` on `FastAPI(...)` constructor reachable in prod → `information-disclosure`
- Custom dependency that calls `get_current_user` but returns a user object without verifying claims → `incorrect-authorization`
- `response.set_cookie(...)` missing `httponly=True` / `secure=True` / `samesite` on authentication cookies → `business-logic-flaw`
