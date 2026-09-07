# Koa Endpoint Enumeration Reference

Koa is a minimal Node.js web framework. **Koa itself has no router** —
`app.use(middleware)` is its only built-in dispatch primitive. Routing comes from
a separate package, almost always **`@koa/router`** (formerly **`koa-router`**).
The consequence: to enumerate Koa endpoints you look for the **router package**,
not the `app` object.

Koa is a **router-mount framework**: a prefix is pinned per `Router` instance (at
construction or via `.prefix(...)`) and an instance can be mounted under an extra
segment with `parent.use("/y", child.routes())`, so the prefix is **per-root,
pre-composed by the main agent** — the main agent composes L1 + the Router's
instance prefix + any mount path and hands the whole segment down; the worker
enumerates that router's handlers and resolves each handler's path.

---

## 1. Identify

- **Dependencies** — `koa` plus a router package: `@koa/router` (or the older
  `koa-router`) in `package.json`.
- **Markers (one grep-able signal each):**
  - `new Koa()` — the app object.
  - `new Router({ prefix: "/x" })` — a router instance (the registration root).
  - `router.get(...)` / `router.post(...)` / … — route registrations.
  - `parent.use("/y", child.routes())` — a router mounted under an extra segment.

---

## 2. Structural traversal — main agent

Find the router instances, derive each one's pre-composed prefix, and hand each
down. The main agent does **not** read handler bodies (§3).

- **L1 Deployment** — Koa has no framework base path; the app usually mounts at
  `/`. A whole sub-app can be mounted under a prefix with `koa-mount`
  (`app.use(mount("/admin", subApp))`) — treat the sub-app as its own root with
  that mount prefix.
- **L3 Registration root** — each `new Router({ prefix: "/x" })` instance is one
  root. Its prefix comes from the construction `{ prefix: "/x" }` **and/or** a
  later `.prefix("/x")` call, **plus** the mount path when the instance is mounted
  via `parent.use("/y", child.routes())`. **The instance prefix AND the mount path
  compose — preserve both** (a child `new Router({ prefix: "/x" })` mounted with
  `parent.use("/y", child.routes())` under a parent `new Router({ prefix: "/api" })`
  yields `/api` + `/y` + `/x`). Grep for them:

  ```bash
  grep -rnE 'new Router\(|\.routes\s*\(\s*\)|\.use\s*\(' --include='*.js' .
  ```

- **Prefix composition** — Koa is a router-mount framework, so the **main agent
  PRE-COMPOSES L1 + the Router's instance prefix + the mount path** and hands the
  whole segment. Example: `new Router({ prefix: "/api" })` mounted with
  `parent.use("/v1", child.routes())` → `/api/v1` handed to the worker; the worker
  appends only the per-route path.

### Dispatch contract

- One worklist entry = **one `Router` instance**.
- Hand each worker: `framework=koa`,
  `prefix=<pre-composed L1 + Router instance prefix + mount path>`,
  `location=<file:line of the `new Router(...)` instance, or its `parent.use(...)`
  mount>`, `scope=<the module(s) defining that router's routes>`.
- Split / merge: one entry per `Router` instance; compose its prefix + mount path
  into the handed prefix. Do **not** over-split one router's routes into many tiny
  scopes.

---

## 3. Handler enumeration — worker

Given one router's scope, enumerate every routed handler and compose the final
endpoint (apply the prefix the main agent handed you).

### Route registration methods (`@koa/router`)

| Function | HTTP Method | Description |
|----------|-------------|-------------|
| `router.get()` | GET | Retrieve data |
| `router.post()` | POST | Create resource |
| `router.put()` | PUT | Replace resource |
| `router.delete()` / `router.del()` | DELETE | Delete resource |
| `router.patch()` | PATCH | Partial update |
| `router.head()` | HEAD | Headers only |
| `router.options()` | OPTIONS | CORS preflight |
| `router.all()` | All → method `"*"` | Match all methods |
| `router.register(path, methods, mw)` | Custom | Explicit method list (comma-joined) |

```javascript
router.get('/users', listUsers);
router.post('/users', createUser);
router.get('/users/:id', getUser);
router.put('/users/:id', updateUser);
router.delete('/users/:id', deleteUser);

// Match all methods -> method "*"
router.all('/webhook', handleWebhook);

// Wire the router into the app — REQUIRED, routes are inert without this
app.use(router.routes());
app.use(router.allowedMethods());
```

> A `Router` whose `.routes()` is never passed to `app.use(...)` registers no
> live endpoints. Still, for auditing, treat every `router.METHOD(...)` call as an
> endpoint unless the router is clearly dead code.

**Method rule:** the method is the verb in the call
(`get`/`post`/`put`/`delete`/`del`/`patch`/`head`/`options`); `router.all(...)` →
method `"*"`; `router.register(path, ['GET','POST'], ...)` → comma-joined methods.

### Named routes

```javascript
// Optional first arg is a route NAME, not a path. Path is then the 2nd arg.
router.get('user-detail', '/users/:id', getUser);   // name="user-detail", path="/users/:id"
```

When the first argument is followed by **another string**, the first is a name and
the **second** is the path. Otherwise the first string is the path.

### `router.use` middleware vs routes

```javascript
// App-level middleware — NOT a route
app.use(async (ctx, next) => { ctx.state.start = Date.now(); await next(); });

// Router-level middleware applied to all of the router's routes — NOT a route
router.use(authMiddleware);

// Path-scoped router middleware — NOT a route
router.use('/admin', authMiddleware);

// Per-route middleware — extra handlers before the final one; the route IS the endpoint
router.get('/protected', authMiddleware, protectedHandler);
```

`app.use(...)` and `router.use(...)` register middleware, **not** endpoints. The
exceptions that *are* endpoints: `app.use(router.routes())` (wires a router in) and
`app.use(mount('/x', subApp))` (mounts a sub-app).

### Path parameters

Record the path **as written** (the auditor matches the registered template):

```javascript
router.get('/users/:id', getUser);                       // single param
router.get('/users/:userId/posts/:postId', getPost);     // multiple params
router.get('/users/:id?', getUserOptional);              // optional param
router.get('/files/(.*)', serveFile);                    // path-to-regexp wildcard
router.get(/^\/legacy\/.*/, legacyHandler);              // raw RegExp path
```

### Compose the prefix onto every path

The main agent handed you the already-composed prefix (L1 + Router instance prefix
+ mount path). Append each route's own path to it and record the **already-composed**
full endpoint — e.g. handed prefix `/api/v1` + `router.get('/users', ...)` →
`/api/v1/users`.

### `region` — the final handler's function body

The handler is the **last argument** of the registration call (any earlier
function arguments are per-route middleware). Anchor the `region` at that final
handler's function body:

```javascript
// Koa handler — single ctx, async, calls next() to continue the chain
async function getUsers(ctx, next) {
    const id = ctx.params.id;                  // path parameter
    const name = ctx.query.name;               // query parameter
    const body = ctx.request.body;             // request body (needs koa-bodyparser)
    ctx.body = { data: users };                // response
}
```

For an inline arrow/function as the last argument, the body is at the registration
site; for a named handler / reference, open that function and record its body.

### Enumeration checklist

- Koa has no built-in router — endpoints come from `@koa/router` / `koa-router`
  instances; work the one router's scope the main agent handed you.
- Method = the verb in the call; `router.all(...)` → `"*"`;
  `router.register(path, ['GET','POST'], ...)` → comma-joined.
- Named-route form: `router.get(name, path, handler)` — path is the 2nd string when
  two strings precede the handler.
- `app.use(...)` / `router.use(...)` are middleware, except `app.use(router.routes())`
  and `koa-mount`.
- Record the path **as written** (`:id`, `:id?`, `(.*)`) — do not normalize.
- Compose the handed prefix onto every path; record the full endpoint.
- `region` = the **final handler** (last argument) function body, not a middleware
  argument and not the registration line itself.
