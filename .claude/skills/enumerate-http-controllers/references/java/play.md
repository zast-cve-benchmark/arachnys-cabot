# Play Framework Endpoint Enumeration Reference

The Play Framework (Java/Scala) is unusual among Java web frameworks: routing is
**not** annotation-driven. All routes are declared in a plain-text **`conf/routes`**
file, which the build compiles into a `Routes` class. Controller methods are
referenced from that file by fully-qualified name. The `conf/routes` file is the
registration root, and each non-comment line is one endpoint; controller classes only
supply the method body (the `Region`). The route prefix is per-root (an `->` include
mounts a sub-routes file under a known prefix), so the main agent pre-composes
L1 + the include mount and hands the whole segment to each worker.

---

## 1. Identify

One grep-able signal each — both agents read this, keep it short.

- **Framework marker** — the **`conf/routes`** file itself. Its existence (a plain
  text route table under `conf/`) is the defining signal that Play is in use.
- **Route-line marker** — lines of the form `GET  /x  controllers.Foo.bar`: three
  whitespace-separated columns (HTTP method, URL path, FQN controller call).
- **Sub-router marker** — `->  /x  p.Routes` lines, which include another routes
  file (a sub-router) under a prefix.

```regex
# Route line: METHOD  PATH  controller.call
^\s*(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s+(\S+)\s+(\S+)
# Sub-router include
^\s*->\s+(\S+)\s+(\S+)
```

---

## 2. Structural traversal — main agent

The main agent walks the layer checklist and descends to the registration-root
layer — the `conf/routes` file — then hands a worker the file as scope. There is no
annotation/class layer to traverse here: each routes line is a complete route, and a
`-> /x SubRouter` line mounts a sub-routes file under `/x`.

### L1 Deployment

A Play app's context-path (if any) applies before any code — declared in the
deployment/server config. If none is declared, the app mounts at `/` and L1
contributes nothing.

### L3 Registration root

The root is the **`conf/routes` file itself** — plus any sub-routes file it includes
via `->`. Each non-comment line in the file is a route. A line whose third column is
`->` mounts a sub-router under a prefix:

```routes
# Include another routes file / generated router under a prefix
->     /api/v1                   api.v1.Routes
->     /admin                    admin.Routes
```

`-> /prefix SomeRouter` composes `/prefix` onto every route the included router
declares. This is the Play prefix mechanism — treat each included routes file as its
own registration root carrying that mount prefix. The most common case is the
`sub-projects` / modules layout, where `api.v1.Routes` is generated from another
`routes` file (`conf/*.routes`, `modules/*/conf/routes`).

### Prefix composition

Because the prefix is per-root and known at the include site, the **main agent
pre-composes** it: L1 deployment prefix + the include mount prefix (usually `""` for
the main `conf/routes`, `/x` for a `-> /x SubRouter` include) form the segment handed
to the worker. The routes file is the scope; the worker reads each line and appends
the line's own path.

### Dispatch contract

- One worklist entry = one `conf/routes` file — the main `conf/routes`, plus one
  entry per sub-routes file included via `->` (each under its mount prefix).
- Hand each worker: `framework=play`,
  `prefix=<L1 deployment + the include mount prefix, usually "" for the main routes
  file>` (per-root framework → the mount prefix is known at the include site, so
  pre-compose it),
  `location=<the conf/routes file path>`,
  `scope=<that conf/routes file + the controllers package it references>`.
- Split / merge: split one entry per routes file — the main `conf/routes` plus each
  `->` include with its mount prefix. Do **not** over-split per line: one worker reads
  the whole routes file at once (each line is a quick lookup; splitting lines across
  workers wastes round-trips).

---

## 3. Handler enumeration — worker

Given one `conf/routes` file as scope and its pre-composed `{prefix}` from the main
agent, parse the file line by line (plain text, not an AST) and emit one endpoint per
non-comment route line.

### Route line format — one line, one endpoint

Each non-comment, non-blank line is one route:

```
METHOD     PATH                          controller.Method(params)
```

Three whitespace-separated columns: HTTP method, URL path, and the controller call.

```routes
# conf/routes  — comments start with #

GET     /                             controllers.HomeController.index()
GET     /users                        controllers.UserController.list()
POST    /users                        controllers.UserController.create()
GET     /users/:id                    controllers.UserController.show(id: Long)
PUT     /users/:id                    controllers.UserController.update(id: Long)
DELETE  /users/:id                    controllers.UserController.delete(id: Long)
```

**Enumeration rule:** each route line → one endpoint. Method = column 1 (`GET`,
`POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`, `OPTIONS` are all valid — every method is
explicit, one line each; there is no "match all" token), path = column 2 (compose the
`{prefix}` from the worklist onto it), handler = column 3. The `Region` is the
definition of the method named in column 3, located in that controller class.

`->` lines are **includes, not endpoints** — they were already split out as their own
worklist entry by the main agent (§2); do not emit an endpoint for them.

### Path parameters

```routes
# :name  — single dynamic segment (no slashes)
GET   /users/:id                 controllers.UserController.show(id: Long)

# *name  — wildcard, matches the rest INCLUDING slashes
GET   /files/*path               controllers.FileController.serve(path: String)

# $name<regex>  — regex-constrained segment
GET   /items/$id<[0-9]+>         controllers.ItemController.get(id: Long)

# Query parameters declared in the method call's parameter list
GET   /search                    controllers.SearchController.run(q: String, page: Int ?= 1)
```

Record the path as written in column 2 (`:id`, `*path`, `$id<...>` syntax kept).
Parameters in the method-call parentheses that are not in the path are query
parameters.

### Static assets

```routes
GET   /assets/*file              controllers.Assets.versioned(path="/public", file: Asset)
```

The `Assets` controller serves static files — a catch-all, not application logic,
but still a routed endpoint.

### Controller classes — the Region

Controllers are referenced by FQN from `conf/routes`. The method named in column 3 is
the routed handler; its method body is the `Region`. Read the controller class to
locate it.

```java
// app/controllers/UserController.java
package controllers;

import play.mvc.Controller;
import play.mvc.Result;
import play.mvc.Http;

public class UserController extends Controller {

    // Referenced by: GET /users  controllers.UserController.list()
    public Result list() {
        return ok(Json.toJson(users));
    }

    // Path param bound from /users/:id
    public Result show(Long id) {
        return ok(Json.toJson(findUser(id)));
    }

    // Request body / form access
    public Result create(Http.Request request) {
        JsonNode body = request.body().asJson();
        return created(...);
    }
}
```

Method-based controllers extend `play.mvc.Controller`; each routed method
returns `play.mvc.Result` (or `CompletionStage<Result>` for async). AST patterns for
locating them within the scope:

```java
// Controller classes
ast_grep_search(pattern='class $NAME extends Controller { $$$ }', lang='java')

// Routed methods return Result
ast_grep_search(pattern='public Result $METHOD($$$) { $$$ }', lang='java')
ast_grep_search(pattern='public CompletionStage<Result> $METHOD($$$) { $$$ }', lang='java')
```

Key files to check:

| Path | Purpose |
|------|---------|
| `conf/routes` | **Primary** — all route declarations |
| `conf/*.routes` / `modules/*/conf/routes` | Sub-router routes files (included via `->`) |
| `app/controllers/` | Controller classes |
| `app/controllers/**/*Controller.java` | Controller naming convention |

### Dependency-injected routes (`@`)

```routes
# A leading @ means the controller instance is resolved by the DI container.
GET   /users                     @controllers.UserController.list()
```

The `@` prefix only changes instantiation — the endpoint and method resolution
are identical.

### Filters & action composition (not endpoints)

Play's request interception is done via `play.mvc.EssentialFilter` /
`play.http.HttpFilters`, and via action-composition annotations
(`@With(...)`, `@Security.Authenticated`). These wrap routed methods — they are
not themselves endpoints.

### Enumeration checklist

- The `conf/routes` file is the registration root — each route line is exactly one endpoint.
- Method = column 1 (always explicit, never "match all"), path = column 2 (compose the `{prefix}`), handler = column 3 (an FQN method).
- The `Region` is the column-3 method's definition inside its controller class — read the controller to locate it.
- `-> /prefix SomeRouter` includes a sub-router — it is a separate worklist entry, not an endpoint.
- A leading `@` on the controller call changes only DI instantiation, not the endpoint.
- Path syntax: `:seg` single segment, `*seg` greedy wildcard, `$seg<regex>` constrained — keep as written.
- Filters and `@With`/`@Security` action composition are interceptors, not endpoints.
