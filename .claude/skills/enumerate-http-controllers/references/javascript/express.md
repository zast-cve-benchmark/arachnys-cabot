# Express.js Endpoint Enumeration Reference

Express.js defines endpoints with `app.METHOD(...)` calls on the application and
`router.METHOD(...)` calls on `express.Router()` instances mounted under a path via
`app.use("/x", router)`. It is a **router-mount framework**: each Router binds a set
of handlers under the prefix it is mounted at, and mounts compose through nested
`use`.

Routing here is **per-root, pre-composed by the main agent**: each Router (or the
app itself) is a registration root, so the main agent composes the deployment base +
the mount prefix and hands the whole segment down; the worker enumerates that root's
handlers and resolves each handler's path from the route literal at its call site.

---

## 1. Identify

- **Dependency** — `express` in `package.json`.
- **App / Router creation** — `express()`, `express.Router()`.
- **Mount marker** — `app.use("/x", router)`.
- **Route markers** — `app.get/post(...)` (and the other verbs) on the app,
  `router.get/post(...)` on a Router.

Any of these confirms Express is the router in use.

---

## 2. Structural traversal — main agent

The main agent finds the app, lists the Routers and where each is mounted, and
composes the prefix prepended at mount time. It stops there — it does **not** read
handler bodies (that is the worker's job, §3).

- **L1 Deployment** — Express mounts at `/` in most apps (any mount path is
  possible); there is usually no framework base path. A reverse-proxy prefix, if
  any, lives in deploy config, not the source.
- **L3 Registration root** — the **app** itself (for routes registered directly via
  `app.METHOD`) and **each `express.Router()`** mounted via `app.use("/x", router)`.
  A Router carries no prefix of its own — its prefix is the path it is mounted at,
  and **mounts compose through nested `use`** (a Router mounted inside another
  Router's subtree inherits the outer mount prefix). Preserve this composition.

  Find the roots with:

  ```bash
  grep -rnE 'express\.Router\s*\(' .
  grep -rnE 'app\.use\s*\(' .
  grep -rnE '\.(get|post|put|delete|patch|all)\s*\(' .
  ```

- **Prefix composition — MAIN PRE-COMPOSES.** The main agent composes L1 + the
  mount prefix (composing nested mounts) and hands the whole segment to the worker.
  Mounting is the cross-file case: the Router is often built in another module
  (`routes/users.js`), with its mount path as the composed prefix.

  ```javascript
  // app.js
  const usersRouter = require('./routes/users');
  app.use('/api/v1/users', usersRouter);     // prefix "/api/v1/users", sub-module is the scope
  app.use('/api/v2/users', usersRouter);     // same Router mounted again -> distinct prefix

  app.get('/health', healthHandler);         // app root: prefix "" -> /health
  ```

### Dispatch contract

- One worklist entry = one Router (or the app root for routes registered directly
  on it).
- Hand each worker: `framework=express`,
  `prefix=<pre-composed L1 deployment + the mount prefix>`,
  `location=<the app.use mount call site, or the Router decl, file:line>`,
  `scope=<the module(s) defining that Router's routes>`.
- Split / merge: one entry per Router (compose nested mount prefixes into the
  parent's segment). A Router mounted at several paths is several endpoints
  downstream, but the worker fans that out — give it one entry per Router. Do NOT
  over-split one Router's handler list into many tiny scopes (each worker is one
  round-trip).

---

## 3. Handler enumeration — worker

Given one root's scope, enumerate every routed handler and compose the final
endpoint (apply the prefix the main agent handed you): `path = prefix + the route
literal at the call site`, method from the verb in the call.

### Routed handlers — method from the verb

Express exposes one function per HTTP verb on both `app` and a Router; the method is
the verb in the call name. A method-agnostic `.all(...)` → record method `"*"`.

| Function | HTTP Method | Notes |
|----------|-------------|-------|
| `app.get()` / `router.get()` | GET | Retrieve data |
| `app.post()` / `router.post()` | POST | Create resource |
| `app.put()` / `router.put()` | PUT | Replace resource |
| `app.delete()` / `router.delete()` | DELETE | Remove resource |
| `app.patch()` / `router.patch()` | PATCH | Partial update |
| `app.options()` / `router.options()` | OPTIONS | CORS preflight |
| `app.trace()` / `router.trace()` | TRACE | Diagnostic trace |
| `app.all()` / `router.all()` | `"*"` | Matches all methods — record method `"*"` |

All follow the same signature: `app.METHOD(path, callback [, callback ...])`.

```javascript
app.get('/users', (req, res) => { ... });          // GET    /users
app.post('/users', (req, res) => { ... });         // POST   /users
app.put('/users/:id', (req, res) => { ... });      // PUT    /users/:id
app.delete('/users/:id', (req, res) => { ... });   // DELETE /users/:id
app.all('/secret', (req, res, next) => { ... });   // *      /secret

// On a Router (relative to its mount prefix):
router.get('/', listUsers);                         // GET  <prefix>/
router.get('/:id', getUser);                        // GET  <prefix>/:id
router.post('/', createUser);                       // POST <prefix>/
```

### Route chaining — `app.route(path)` / `router.route(path)`

A `.route(path)` chain registers one endpoint per chained verb method, all sharing
the same path:

```javascript
app.route('/book')
    .get((req, res) => { ... })       // GET    /book
    .post((req, res) => { ... })      // POST   /book
    .put((req, res) => { ... });      // PUT    /book

app.route('/book/:id')
    .get((req, res) => { ... })       // GET    /book/:id
    .delete((req, res) => { ... });   // DELETE /book/:id
```

Record one endpoint per chained method.

### Middleware vs route handler

`app.use(...)` / `router.use(...)` **with no HTTP method** attaches middleware, not
a route — it is **not an endpoint**, whether global (`app.use(fn)`) or path-scoped
(`app.use('/api', fn)`). (The one exception that IS structural is `app.use('/x',
router)`, which is a mount, handled by the main agent in §2 — not a handler here.)

Per-route middleware chained ahead of the handler **does not change the endpoint**:
record the route at its path; the leading callbacks are just middleware.

```javascript
// Middleware only — NOT endpoints:
app.use((req, res, next) => { req.requestTime = Date.now(); next(); });
app.use('/api', (req, res, next) => { /* api-key check */ next(); });

// Route with per-route middleware — ONE endpoint at the path:
app.get('/user/:id', loadUser, (req, res) => { ... });            // GET /user/:id
app.get('/user/:id/edit', loadUser, checkAuth, (req, res) => {}); // GET /user/:id/edit
```

### Path-parameter syntax — record as written

| Syntax | Example | Notes |
|--------|---------|-------|
| `:name` | `/user/:id` | Named parameter |
| `:name?` | `/user/:id?` | Optional parameter |
| multiple `:` | `/users/:userId/posts/:postId` | Compose normally |
| `:from-:to` | `/users/:from-:to` | Param separators |
| `*` / `*name` | `/files/*file`, `/api/{*splat}` | Wildcard / splat (Express 5 `{*name}`) |
| RegExp | `/user\/(\d+)/` | Regex route; params in `req.params[0]` |

Record the path **as written** — the auditor matches on the registered template,
not a normalized form.

### Locating handler functions

The handler passed to a route may be inline or a reference; follow it to its body
for the region:

```javascript
app.get('/endpoint', (req, res) => { ... });                 // inline
function handler(req, res) { ... }
app.get('/endpoint', handler);                               // named reference
const UserController = require('./controllers/user');
app.get('/users', UserController.list);                      // controller export
app.post('/endpoint', async (req, res, next) => { ... });    // async handler
```

Handlers commonly live in `routes/`, `controllers/`, `api/`, or the main
`app.js` / `server.js`.

### `region` — anchor at the handler body

Record the `region` at the handler function's body, not the registration line. For
a named handler, method-reference, or controller export (`app.get('/users',
UserController.list)`), open that function and span its body. For an inline arrow
(`app.get('/x', (req, res) => { ... })`), the body is at the registration site, so
recording there is correct only because the body is there.

### Enumeration checklist

- `path = prefix + route literal`; method = the verb in the call.
- `.all(...)` → method `"*"`.
- `.route(path).get().post()` → one endpoint per chained method.
- `app.use(...)` / `router.use(...)` with no method is **middleware, not an
  endpoint** (but `app.use('/x', router)` is a mount — handled by the main agent).
- Per-route middleware chained before the handler does not change the endpoint.
- Record the path **as written** (`:id`, `:id?`, `*`) — do not normalize.
- `region` = the handler function's body span, never the registration line.
