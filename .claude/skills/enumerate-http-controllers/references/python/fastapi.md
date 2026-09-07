# FastAPI Endpoint Enumeration Reference

FastAPI is a decorator-based Python web framework, and a **router-mount**
framework: routes attach to a `FastAPI` app or to an `APIRouter`, and routers
are mounted onto the app (or onto each other) with `app.include_router(...)`.
Prefixes compose across the mount chain, so this is a **per-root, pre-composed**
framework — the MAIN agent pre-composes L1 + the `APIRouter` prefix + the
`include_router` prefix and hands the worker the whole segment.

---

## 1. Identify

- **Dependency** — `fastapi` (in `requirements.txt` / `pyproject.toml` / imports).
- **App / router construction** — `FastAPI()`, `APIRouter(...)`.
- **Route decorators** — `@app.get(...)`, `@router.post(...)`, etc.
- **Router mounting** — `app.include_router(...)`.

Any one of these confirms FastAPI is in use.

---

## 2. Structural traversal — main agent

Walk the layers for FastAPI; stop at the registration root and dispatch a worker
below it. Do **not** read individual handler bodies (worker territory, §3).

**L1 Deployment.** A base path applied before any code, usually `/` (none). It
can be set by `FastAPI(root_path="/api")` or by mounting the app under a sub-path
(`app.mount(...)` / a reverse-proxy prefix). Record it as the L1 prefix.

**L3 Registration roots.** Two kinds of root:

- **The app itself**, for routes attached directly with `@app.get/post/...`. Its
  prefix is just L1.
- **Each `APIRouter`**, for routes attached with `@router.get/post/...`. A
  router's prefix comes from **both** of:
  - the `prefix=` passed to its constructor — `APIRouter(prefix="/items")`, **and/or**
  - the `prefix=` passed when it is mounted — `app.include_router(router, prefix="/api/v1")`.

  **These COMPOSE.** A router declared `APIRouter(prefix="/items")` and mounted
  `app.include_router(router, prefix="/api/v1")` serves its routes under
  `/api/v1/items`. Routers can also nest (`parent.include_router(child)`), and
  each mount level contributes its own `prefix=` to the chain.

**Prefix composition.** FastAPI is a router-mount framework, so the MAIN agent
**pre-composes the whole segment**: L1 prefix + the `APIRouter(prefix=...)` + the
`include_router(prefix=...)` (composing every nesting level), and hands that
single composed prefix to the worker.

```text
root_path="/api"  +  APIRouter(prefix="/items")  +  include_router(prefix="/v1")
  ->  composed prefix handed to worker = /api/v1/items
```

Grep to find the roots and mounts:

```regex
include_router|APIRouter\(|@app\.|@router\.
```

```bash
grep -rnE 'include_router|APIRouter\(|@app\.|@router\.' --include='*.py' .
```

Useful files to check: `main.py` (entry point), `app.py` (app factory),
`routers/` or `routes/`, `api/`, `endpoints/`.

When you find `include_router()`, trace the imported router to its module so the
worker's scope covers where that router's routes are defined:

```python
from app.routers import users, items
app.include_router(users.router, prefix="/users")
app.include_router(items.router, prefix="/items")
```

### Dispatch contract

- One worklist entry = **one `APIRouter`** (or the app root for `@app.*` routes).
- Hand each worker: `framework=fastapi`,
  `prefix=<pre-composed L1 + APIRouter(prefix=...) + include_router(prefix=...)>`,
  `location=<file:line of the include_router call / the APIRouter declaration>`,
  `scope=<the module(s) defining that router's routes>`.
- Split / merge: one entry per router; compose nested `include_router` prefixes
  into the one segment you hand down. Do NOT over-split one router's route list
  into many tiny scopes (each worker is one round-trip).

---

## 3. Handler enumeration — worker

Given one root's scope (the app root or one `APIRouter`), enumerate every routed
handler and compose the final endpoint with the prefix the main agent handed you.

### 3.1 Route decorators

Routes are HTTP-method decorators on the app or the router; the **method is the
verb** in the decorator name.

| HTTP Method | App decorator | Router decorator |
|-------------|---------------|------------------|
| GET     | `@app.get()`     | `@router.get()`     |
| POST    | `@app.post()`    | `@router.post()`    |
| PUT     | `@app.put()`     | `@router.put()`     |
| DELETE  | `@app.delete()`  | `@router.delete()`  |
| PATCH   | `@app.patch()`   | `@router.patch()`   |
| OPTIONS | `@app.options()` | `@router.options()` |
| HEAD    | `@app.head()`    | `@router.head()`    |
| TRACE   | `@app.trace()`   | `@router.trace()`   |

Decorators take a `path` (required) plus optional `response_model`,
`status_code`, `tags`, `dependencies`, `summary`, `description`, `deprecated`.
Only the `path` matters for enumeration.

```python
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
async def list_users():
    return []

@router.get("/{user_id}")
async def get_user(user_id: int):
    return {"id": user_id}
```

**WebSocket routes** are endpoints too — `@app.websocket("/ws")` /
`@router.websocket("/ws")` decorate a WebSocket handler.

### 3.2 Compose the final path

The endpoint path = the composed prefix the main agent handed you + the decorator
path argument. For example, a router handed prefix `/api/v1/users` with a
`@router.get("/{user_id}")` route yields endpoint `/api/v1/users/{user_id}`.

### 3.3 Path parameters

Path parameters use `{name}` syntax; a `{name:path}` converter matches a
multi-segment trailing path. Record the path **as written** (the auditor matches
the registered template, not a normalized form):

```python
@app.get("/items/{item_id}")                 # /items/{item_id}
@app.get("/users/{user_id}/items/{item_id}") # multiple path params
@app.get("/files/{file_path:path}")          # multi-segment trailing path
```

### 3.4 Routes are still endpoints with dependency injection

A path-operation function with injected dependencies (`Depends(...)`,
`Annotated[..., Query()]`, a Pydantic body model, etc.) is still a routed
endpoint — record it. Dependencies and request-shaping parameters do not change
that the decorated function is the handler.

```python
@app.post("/items/")
async def create_item(item: Item, token: str = Depends(verify_token)):
    return item
```

### 3.5 Class-based routes

If the project uses a class-based view extension (e.g. `@cbv` from
`fastapi-utils`), each routed method of the class is an endpoint. The class may
carry a router/prefix; compose it the same way and record each method.

### 3.6 Region anchoring

Record the `region` at the **path-operation function body** — the decorated
handler function — not the decorator line or the `include_router` call.
`start_line` = the function's signature line (`def`/`async def`), `end_line` =
its closing body line.

### 3.7 Locating handlers

Search for route decorators with AST or regex tools:

```python
ast_grep_search(pattern='@app.get($PATH)', lang='python')
ast_grep_search(pattern='@router.post($PATH)', lang='python')
ast_grep_search(pattern='@app.websocket($PATH)', lang='python')
ast_grep_search(pattern='@router.websocket($PATH)', lang='python')
```

```regex
@(app|router)\.(get|post|put|delete|patch|options|head|trace|websocket)\s*\(
```

### 3.8 Enumeration checklist

- One endpoint per route decorator; method = the decorator verb.
- Final path = composed prefix (handed by the main agent) + decorator path.
- Record path params as written (`{id}`, `{id:path}`).
- Dependency-injected and class-based (`@cbv`) routes are still endpoints.
- WebSocket routes (`@app.websocket`/`@router.websocket`) count.
- `region` = the path-operation function body, never the decorator or
  `include_router` line.
