# Meteor / Restivus (Rocket.Chat-style) Endpoint Enumeration Reference

This covers Meteor applications that expose a REST API through a **Restivus-derived
`API` object** (`nimble:restivus` / the Rocket.Chat API). The framework is **not**
Express/Koa/Nest: there is no `router.get(...)`, no `app.use(...)`, no file-system
routing. Every endpoint is registered by a call to `API.<instance>.addRoute(...)`.

Its distinctive shape: **routes are scattered across the whole tree, with one
worker per directory.** There is **no central route table** — every
`API.<instance>.addRoute("path", ...)` call site is its own registration root, and
those call sites sit in feature modules all over the source tree (NOT in one `api/`
folder). The prefix is carried by the `API` *object*, not the file's directory, so
the main agent must build the worklist from a **project-wide grep** for `.addRoute(`
and pre-compose the API-object prefix.

---

## 1. Identify

Meteor + Restivus (`nimble:restivus`, or the Rocket.Chat API built on it). One
grep-able signal each:

- **Construction** — `new Restivus({...})` (or a `createApi(...)` helper / an
  `APIClass extends Restivus`) building the `API` object.
- **Route registration** — `API.<instance>.addRoute(...)` call sites
  (`.addRoute(` is the registration primitive — there is no router/app object).
- **The `API` object** — exports carrying `.v1` / `.default` members (`API.v1`,
  `API.default`); locate the module that constructs them with
  `new APIClass(...)` / `createApi(...)`.

---

## 2. Structural traversal — main agent

The main agent builds the worklist project-wide and pre-composes the prefix. It
does **not** read handler bodies (that is the worker's job, §3).

**L1 Deployment.** None for most Meteor apps — the API mounts at `/` (the
`apiPath`/`version` below contribute the only URL prefix). In a monorepo the
source root may be a subdir (`apps/<name>/`); run the grep below from there.

**L3 Registration root — there is NO central route table.** Every
`API.<instance>.addRoute("path", ...)` call site is its own root, and the call
sites are **scattered across feature modules all over the tree** — NOT collected in
one `api/` folder. *Where* a call sits is purely an author's stylistic choice
(the prefix is decoupled from the file location), so a given project may mix any of
these conventions at once — none inferable from directory names:

1. **Central registry.** A few files call `addRoute` for everything, or an index
   imports route modules purely for their registration side effects. Confirm
   centrality with the grep — "looks central" is not "is central".
2. **Per-feature co-location.** Each domain/feature module registers its own
   routes next to that feature's business logic, far from any `api/` directory.
   This is the dominant source of scatter and the most common reason endpoints
   get missed.
3. **Edition / tier split.** Core, optional, paid, or plugin tiers live in
   separate top-level subtrees but register onto the **same** `API` object — their
   routes share the `/api/v1/` prefix while living in an unrelated part of the tree.
4. **Dynamic / loop registration.** `addRoute` is called inside a loop, factory,
   or `forEach` over a manifest/config (e.g. generated CRUD). The path argument may
   be a **variable or template**, not a string literal — read the surrounding loop
   to recover the path(s) it expands to.
5. **Held-instance registration.** A class or module holds its own API instance
   (`this.api`, a module-level `const`) built with a different `version`, and
   registers through that. The receiver is not literally `API.v1`; resolve it
   below.
6. **Vendored / base-layer routes.** The Restivus base layer or a vendored package
   may register its own internal endpoints (auth/login/logout, health, etc.).
   These are real endpoints; do not skip a directory just because it looks like
   framework plumbing.

**The prefix comes from the `API` object — not the file's directory.** A file
anywhere in the tree can `import { API }` and call `API.v1.addRoute(...)` to
register a `/api/v1/...` route; the directory contributes nothing to the URL.
**Scoping enumeration to an `api/` directory therefore misses entire feature
areas.** The full path is built in the class's route-name builder (a
`getFullRouteName`-style helper) as:

```
/  +  apiPath ("api/")  +  version + "/" (if the instance has a version)  +  subpath
```

The receiver of `.addRoute(...)` determines the prefix:

| Receiver | Constructed as | Prefix | Notes |
|---|---|---|---|
| `API.v1` | `createApi({ version: 'v1' })` | `/api/v1/` | The overwhelming majority of routes |
| `API.default` | `createApi()` | `/api/` | No version segment |
| a held instance (`this.api`, a local/module var) | `new API.ApiClass({ version: X })` | `/api/{X}/` | A class that builds its own instance with some `version` string |
| any `new API.ApiClass({ version: X })` / `createApi({ version: X })` | — | `/api/{X}/` | Resolve `X`; if no `version`, prefix is `/api/` |

To map a `.addRoute` call to its prefix, resolve the receiver expression (`API.v1`,
`API.default`, `this.api`, a local variable) back to the `createApi(...)` /
`new API.ApiClass(...)` that produced it and read its `version`.

> **Read `apiPath` and `version` from the construction — do not hardcode them.**
> `api/` + `v1` is the common case (and what the table assumes), but both are
> config: a project may set `apiPath` to something else (e.g. `rest/`) or
> omit/rename the version. `API.v1` is a convention, not a guarantee — confirm
> against the actual `createApi(...)` / `new APIClass(...)` arguments. The
> composition formula, not the literal `/api/v1/`, is the source of truth.

**Build the worklist from a project-wide grep — never from the directory layout.**
The registration roots scatter, so derive the worklist mechanically from a single
command and pre-compose the API-object prefix; do not eyeball the tree or guess
which folders matter:

```bash
# Distinct directories with a real .addRoute( call site.
# Exclude build output, minified bundles, deps, tests, and any tool-generated
# metadata dir — those add noise (e.g. minified receivers like `nAPI.v1.addRoute`)
# that is NOT source.
grep -rln "\.addRoute(" . --include=*.ts --include=*.js \
  | grep -vE "/(node_modules|dist|build|\.zast)/|\.min\.|\.spec\.|\.tests?\." \
  | xargs -n1 dirname | sort -u
```

The exact set of directories is whatever the command prints for *this* project — it
depends on which conventions the project uses, and must never be assumed from
another repo. Take the printed list as the contract. Ignore phantom receivers
(single-letter-prefixed names like `nAPI`/`tAPI`) if any slipped past the filter —
those are minified-bundle artifacts, not source routes; real call sites read
`API.v1`, `API.default`, or a held `ApiClass` instance.

A regex for the call site: `\.addRoute\s*\(` — or AST
`ast_grep_search(pattern='$API.addRoute($PATH, $$$)', lang='typescript')`. For each
match, resolve `$API` to a prefix per the table above.

### Dispatch contract

- **One worklist entry = one directory** returned by the project-wide `.addRoute(`
  grep (group the scattered call sites by directory).
- Hand each worker: `framework=meteor-restivus`,
  `prefix=<the API-object prefix, e.g. /api/v1>` (pre-composed from the receiver),
  `location=<a representative addRoute call site in that dir, file:line>`,
  `scope=<that directory's files containing addRoute>`.
- Split: **one entry per directory the grep returns.** Make EVERY directory in the
  Step-1 list its own entry — the worklist-entry count must equal the number of
  directories the grep printed. Do **not** stop after the obvious core `api/`-style
  directory; directories holding feature, optional-tier, integration, or
  vendored-package routes are the easy ones to drop. **Don't miss a directory —
  scattered routes silently drop** if a route-bearing directory has no worker. Keep
  each worker's scope to that directory's own files (a parent and a child directory
  appearing both in the list are separate, independent entries — do not give a
  parent a recursive scope that re-reads the children).

---

## 3. Handler enumeration — worker

Given one directory's scope, enumerate every `addRoute` call and compose the final
endpoint (apply the prefix the main agent handed you). The registration primitive
has an overloaded signature:

```
addRoute(subpath: string | string[], operations)
addRoute(subpath: string | string[], options, operations)
```

- **`subpath`** — the route path relative to the API object's prefix. Either a
  single string or an **array of strings** (one route per element, all sharing the
  same `operations`).
- **`options`** *(optional middle argument)* — `{ authRequired, permissionsRequired,
  validateParams, rateLimiterOptions, ... }`. May be absent; **when the 2nd arg is
  an options object, `operations` is the 3rd arg.**
- **`operations`** — an object whose **keys are lowercase HTTP method names**
  (`get`, `post`, `put`, `delete`, `patch`) mapping to async handler functions.
  **Each `addRoute("path", {options}, { get() {...}, post() {...} })` yields one
  endpoint per HTTP-verb method defined.**

**Endpoint = API prefix + the `addRoute` path.** The verb methods
(`get`/`post`/`put`/`delete`) inside the route definition are the HTTP methods;
the `region` anchors at the **verb method body**.

### Single path, one method

```javascript
// A route registered from some feature module, nowhere near any `api/` folder.
// The directory is irrelevant to the URL; the `API.v1` receiver supplies the prefix.
API.v1.addRoute('reports/:reportId/export', {
    async post() {
        const reportId = this.urlParams.reportId;   // path param
        // ...
    },
});
// -> POST /api/v1/reports/:reportId/export
```

### Single path, multiple methods

```javascript
API.v1.addRoute('widgets.info', { authRequired: true }, {
    async get()  { /* ... */ },
    async post() { /* ... */ },
});
// -> GET  /api/v1/widgets.info
// -> POST /api/v1/widgets.info
```

Emit **one endpoint record per method key.**

### Array subpaths (aliases)

```javascript
API.v1.addRoute(['assets.create', 'files.create'], { authRequired: true }, {
    async post() { /* ... */ },
});
// -> POST /api/v1/assets.create
// -> POST /api/v1/files.create
```

Each array element is its own route. With N subpaths × M method keys, emit **N×M**
endpoint records, all pointing at the same handler region.

### Composing the prefix

The receiver resolves to its version: `API.v1` → `/api/v1/`, `API.default` →
`/api/`, an instance built with `version: X` → `/api/{X}/` (§2). The subpath itself
usually contains **no leading slash** and often uses **dots** as separators
(`widgets.create`, `reports.list`) rather than slashes — but slash segments and
`:params` also occur (`reports/:reportId/export`). **Concatenate verbatim after the
prefix; do not normalize dots to slashes.** For **dynamic** registrations (the path
is a variable/loop), read the surrounding loop/factory to recover the expanded
paths — don't skip the call just because the first arg isn't a string literal.

### Path / query / body parameters

Restivus exposes request data on `this` inside a handler (not via function
arguments):

```javascript
async post() {
    const id   = this.urlParams.reportId;  // :reportId path parameter (Meteor :name style)
    const sort = this.queryParams.sort;    // query string
    const body = this.bodyParams;          // parsed request body
    const uid  = this.userId;              // authenticated user (when authRequired)
}
```

Path parameters use the Meteor `:name` convention inside the subpath string (e.g.
`:reportId`, `:_id`).

### Enumeration checklist

- The endpoint primitive is `API.<instance>.addRoute(subpath, [options],
  operations)` — there is no Express/Koa-style router.
- Resolve each receiver to its version: `API.v1` → `/api/v1/`, `API.default` →
  `/api/`, an instance built with `version: X` → `/api/{X}/`.
- `operations` keys are the HTTP methods (`get`/`post`/`put`/`delete`/`patch`) —
  **one endpoint record per key**; the `region` is that verb method's body.
- `subpath` may be an **array** — one route per element; combine with each method
  key (N×M records).
- Subpaths often use dots (`widgets.create`) and may contain `:param` path segments
  (`reports/:reportId/export`). Concatenate verbatim after the prefix; do not
  normalize dots to slashes.
- For **dynamic** registrations (path is a variable/loop), read the surrounding
  loop/factory to recover the expanded paths — don't skip the call just because the
  first arg isn't a string literal.
- `options` is an optional middle argument — when the 2nd arg is an options object,
  `operations` is the 3rd arg.
