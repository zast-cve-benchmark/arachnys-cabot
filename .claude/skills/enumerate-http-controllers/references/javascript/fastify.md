# Fastify Endpoint Enumeration Reference

Fastify is a high-performance Node.js web framework. Routes are registered on a
Fastify instance; prefix composition is driven by **encapsulated plugins**
registered with `fastify.register(plugin, { prefix })`, and prefixes **compose**
through nested `register` calls.

Routing here is **per-root, pre-composed by the main agent**: each registered
plugin owns its own route namespace under a prefix that is the composition of
every enclosing `register` prefix. A plugin file alone does not reveal its own
prefix — the `register(...)` call site does. So the main agent composes
`L1 + the chain of register prefixes` and hands the whole segment to the worker.

---

## 1. Identify

- **Dependency** — `fastify` in `package.json`.
- **Markers** — one grep-able signal each:
  - `Fastify()` / `require('fastify')()` — the instance is created.
  - `fastify.get(...)` / `fastify.post(...)` (and `put`/`delete`/`patch`/`head`/
    `options`/`all`) — shorthand route registration.
  - `fastify.register(plugin, { prefix: "/x" })` — a prefixed plugin (a
    registration root).
  - `fastify.route({ method, url, handler })` — full-declaration route form.

---

## 2. Structural traversal — main agent

The main agent finds the instance, lists the registered plugins (the registration
roots), and composes the prefix prepended at registration. It stops there — it
does **not** read handlers (that is the worker's job, §3).

- **L1 Deployment** — usually `/` (none). A reverse-proxy / mount base, if any,
  contributes the L1 prefix.
- **L3 Registration root** — each `fastify.register(plugin, { prefix: "/x" })`.
  The plugin's routes mount under that prefix. **Prefixes compose through nested
  registers**: a plugin registered with `{ prefix: '/users' }` *inside* a plugin
  registered with `{ prefix: '/api/v1' }` serves under `/api/v1/users/...`. The
  root Fastify instance (routes registered with no enclosing `register`) is itself
  a root at the L1 prefix.
- **Prefix composition** — Fastify is a **plugin-mount framework**, so the prefix
  is per-root: the main agent **pre-composes `L1 + the chain of register prefixes`**
  and hands the whole segment down. Example: L1 `/` + `register(apiV1, { prefix:
  '/api/v1' })` + nested `register(userRoutes, { prefix: '/users' })` →
  `/api/v1/users`.
  - A plugin wrapped with `fastify-plugin` (`fp(...)`) does **not** open a new
    prefix scope — its routes attach to the registering context's prefix, not a
    child one. Do not treat an `fp(...)`-wrapped plugin as a new root prefix.

Grep for the roots:

```bash
grep -rnE '\.register\s*\(' --include='*.js' --include='*.ts' .   # registration roots (read the { prefix } option)
grep -rnE '\.(get|post|put|delete|patch|head|options|all)\s*\(' --include='*.js' --include='*.ts' .
grep -rnE '\.route\s*\(\s*\{' --include='*.js' --include='*.ts' .
```

### Dispatch contract

- One worklist entry = one registered plugin (or the root Fastify instance).
- Hand each worker: `framework=fastify`,
  `prefix=<pre-composed L1 + the composed chain of register prefixes>`,
  `location=<file:line of the `register(...)` call>`,
  `scope=<the plugin module's routes>`.
- Split / merge: one entry per registered plugin; compose the nested `register`
  prefixes into the prefix you hand down. Do **not** over-split one plugin's routes
  into many tiny scopes (each worker is one round-trip).

---

## 3. Handler enumeration — worker

Given one root's scope (one plugin module), enumerate every routed handler and
compose the final endpoint — apply the prefix the main agent handed you.

### Route forms

- **Shorthand** — `fastify.get/post/put/delete/patch/head/options/all(path, [opts,]
  handler)`. The **method is the verb** in the call; the **path is the first string
  argument**. An options object may sit between path and handler (`fastify.get('/secure',
  { preHandler: authHook }, secureHandler)`) — the handler is still the route's
  handler. `fastify.all(...)` → method `"*"`.
- **Full declaration** — `fastify.route({ method, url, handler })`. The path is the
  **`url`** property and the method is the **`method`** property (do not look for a
  path positional argument here). `method` may be a **string** (`'GET'`) or an
  **array** (`['POST', 'PUT']` → comma-joined `"POST,PUT"`).

Plugin-internal routes register relative to the prefix: a `fastify.get('/', ...)`
inside a plugin handed `/api/users` is endpoint `/api/users/`, and `fastify.get('/:id',
...)` is `/api/users/:id`.

### Path parameters

Record the path **as written** (the find-my-way router):

| Syntax | Example |
|--------|---------|
| `:name` | `/users/:id` |
| multiple params | `/users/:userId/posts/:postId` |
| regex-constrained | `/users/:id(\d+)` |
| `*` / trailing wildcard | `/files/*` (`request.params['*']`) |

Query parameters (`request.query.x`) are not part of the route path.

### Not routes

- `fastify.addHook('onRequest'|'preHandler', ...)` — lifecycle hooks, never routes.
- `fastify.use(...)` — Express-style middleware (via `@fastify/middie` /
  `@fastify/express`), never a route.

### Region

Anchor the `region` at the **handler function body** — the `(request, reply)`
processing function — not at the `.get(...)`/`.route(...)` registration line. If
the handler is a method-reference or named function, follow it to its definition
and record its body.

```javascript
async function getUsers(request, reply) {
    const id = request.params.id;              // path parameter
    const name = request.query.name;           // query parameter
    const body = request.body;                 // request body (auto-parsed)
    reply.send({ data: users });               // response (or `return { ... }`)
}
```

### Enumeration checklist

- Shorthand form: method = the verb, path = the first string argument, one endpoint
  per call.
- `route({...})` form: path = the `url` property, method = the `method` property
  (string, or array → comma-joined).
- `fastify.all(...)` → `"*"`; `method: ['A','B']` → `"A,B"`.
- Compose the prefix the main agent handed you (already the L1 + composed register
  chain) onto every path; a plugin file does not state its own prefix.
- `fastify-plugin` (`fp(...)`)-wrapped plugins do **not** open a new prefix scope.
- `addHook(...)` and `use(...)` are hooks/middleware, not endpoints.
- Record the path as written (`:id`, `*`, regex) — do not normalize.
- `region` = the handler function body, never the registration line.
