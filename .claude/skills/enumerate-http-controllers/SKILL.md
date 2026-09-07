---
name: enumerate-http-controllers
description: Enumerate all API endpoints/controllers in a web project and output structured JSON. Use when user asks to "enumerate controllers", "list all API endpoints", "find all routes", "extract API handlers", or analyze web project structure for security auditing.
---

# Enumerate HTTP Controllers

## Task

Traverse the codebase to extract all http API endpoints and the definition locations of their corresponding controller methods.

---

## Arguments

- **code_language** (optional) — the project's language (e.g. `java`, `python`). Lets workers skip dependency-file detection; if absent, self-detect.

---

## Expected Results

One recorded entry per routed handler — its endpoint, method, and source location.

**You (the main agent) never record anything yourself — every entry is recorded by an `enumerate-http-controllers-worker` sub-agent.** Your job is to locate *where* the controllers live and dispatch a worker per location; the worker reads those files and records each handler.

---

## Workflow

### 1. Identify the framework(s)

The framework is almost always already specified in the auto-loaded `CLAUDE.md` (`## Stack` / `## Auth`) or the user's input — trust it. **Only if neither states it,** dispatch a sub-agent (`Agent` tool) to identify the framework(s); don't re-derive the stack yourself by sweeping the tree.

Expect **multiple surfaces** — many projects run more than one at once: REST API + server-rendered UI, annotation framework + imperative code-registered router, or separate admin/public modules. Enumerate every surface; missing one silently zeroes it. If no annotation framework matches, routing is **imperative** (handlers registered in code at startup) — still endpoints, not none. (A GraphQL `/graphql` surface is **not** your job — the separate `enumerate-graphql-resolvers` enumerator covers it concurrently.)

*DO NOT* open any of step 2's reference docs until you actually understand the frameworks in use.

### 2. Load the matching reference — and only that one

Now that the project's web framework(s) are clear, read the relevant reference doc(s). You (the main agent) read each reference's **§1 Identify + §2 Structural traversal** — §3 Handler enumeration is the worker's half, skip it. 

#### Python
- [Flask](references/python/flask.md) — Route decorators, Blueprints
- [FastAPI](references/python/fastapi.md) — Decorators, APIRouter
- [Django](references/python/django.md) — Views, ViewSets
- [Tornado](references/python/tornado.md) — RequestHandler classes

#### Java
- [Spring Boot](references/java/spring.md) — Annotations, mappings
- [JAX-RS](references/java/jaxrs.md) — Path annotations
- [JFinal](references/java/jfinal.md) — Convention routing, @Action, AutoBindRoutes
- [Struts2](references/java/struts2.md) — Action mappings, namespaces
- [Servlet](references/java/servlet.md) — @WebServlet / web.xml, doXxx methods
- [DWR](references/java/dwr.md) — Direct Web Remoting AJAX services (`dwr.xml` / `@RemoteProxy`, mounted at `/dwr`); a common **second surface** alongside Spring MVC
- [Play](references/java/play.md) — conf/routes file
- [Imperative / no-annotation routing](references/java/imperative-routing.md) — Netty/Vert.x/Undertow/Spark/WebFlux-functional and other code-registered routers; use when no annotation framework matches

#### JavaScript/TypeScript
- [Express](references/javascript/express.md) — Router methods
- [NestJS](references/javascript/nestjs.md) — Controllers, decorators
- [Next.js](references/javascript/nextjs.md) — App Router, Pages Router
- [Koa](references/javascript/koa.md) — @koa/router instances
- [Fastify](references/javascript/fastify.md) — Plugin-prefixed routes
- [Meteor / Restivus](references/javascript/meteor-restivus.md) — Rocket.Chat-style `API.addRoute`; prefix carried by the `API` object, routes scattered across the whole tree

#### Go
- [Gin](references/go/gin.md) — Router groups
- [Echo](references/go/echo.md) — Route registration
- [gorilla/mux](references/go/gorilla.md) — Subrouters, .Methods() matcher
- [Fiber](references/go/fiber.md) — Route groups
- [chi](references/go/chi.md) — Route / Mount / Group composition
- [net/http](references/go/nethttp.md) — Standard-library ServeMux (no framework)

#### PHP
- [Raw / file-as-endpoint](references/php/raw-php.md) — PHP with no router → every `.php` file is an endpoint

#### Fallback — no named framework matched

If step 1 found none of the frameworks above, the routes are registered
**imperatively** in code rather than by annotations/config. Do not stop. Use the
imperative-routing reference for the language and apply its "find the registration
root" technique:

- **Go** → [net/http](references/go/nethttp.md) (already the imperative case).
- **Java** → [Imperative routing](references/java/imperative-routing.md).
- **Other languages** → no dedicated file yet; apply the same technique by analogy
  (locate the server bootstrap → the route-registration calls → read path+method
  from the call site, a branched front-handler, or a handler's spec object), and
  read the closest imperative reference above as a model.

The reference covers both how registration roots are declared (needed when you map roots in step 3) and how individual handler methods are recognized (needed when the workers read handlers in step 4). One read is enough; don't reopen it just to refresh memory — re-derive from the worklist instead.

If the framework is Java, **also** read [Java Project Structure](references/java/project-structure.md) alongside the framework reference — it gives the controller **search strategy** for multi-module projects. (The module map itself — which modules exist and which host a web surface — comes from the primer's `## Layout`; see L2 in step 3.)

### 3. The top-down layer model (walk these for every framework)

Compose every endpoint from four layers, descending top-down. The main agent owns
L1–L3 (structural); below L3 it dispatches a worker for L4.

- **L1 Deployment** — context-path / servlet-mapping / framework mount / reverse-proxy
  prefix, from config files. **Per module**: apply the prefix from the config of the
  *same module that hosts the registration root you are enumerating* — the API
  module's prefix prefixes the API, not a UI/console module's. Compose all deployment
  layers that module's config declares.
  - **Evidence-cited, never guessed.** Every L1 segment must come from a config you
    actually read, with a `file:line`. **Never invent a conventional base** (`/api`,
    `/v1`, `/rest`) because "it looks like a REST app" — a guessed prefix is *both* a
    miss (the real path is wrong) *and* a false positive (you emit an unserved path).
    The common L1 sources to grep for: a Jersey/RESTEasy servlet `<url-pattern>` in
    `web.xml` (strip `/*`), `@ApplicationPath`, Spring `server.servlet.context-path`,
    a CXF `cxf.path` + `setAddress`, a Jetty/Tomcat `contextPath`. The framework
    reference (and `project-structure.md` for Java) says which config is which.
  - **Trace the mount chain before concluding `prefix=""`.** For **router-mount**
    frameworks (FastAPI, Flask, Express, Django, Spring-with-context-path…) the base
    prefix usually IS in the code — not in a config file — at the **mount/registration
    site**, away from the handler. Follow it: FastAPI `app.include_router(r, prefix=…)`
    / `APIRouter(prefix=…)`, Flask `register_blueprint(bp, url_prefix=…)`, Express
    `app.use("/x", router)`, Django `include("app.urls")`, Spring
    `server.servlet.context-path`. A bare `APIRouter()` / `Blueprint()` with no
    constructor prefix gets its base from the `include_router` / `register_blueprint`
    call that mounts it — open that aggregation file. **Only after tracing the full
    mount chain and finding no prefix is `prefix=""` correct.** Defaulting to `""`
    without following the mount chain drops a real base (the worse, more common error).
  - **Keep a stable mount; drop only a deploy-time default.** Apply an L1 prefix when
    it is the app's own **stable, fixed** mount — a Jetty/Tomcat `contextPath` the app
    always deploys under (e.g. a console UI always at `/console`), an in-app config
    prefix, or a framework mount (JAX-RS `cxf.path`). Record `prefix=""` **only** when
    the descriptor is genuinely a deploy-time *default* that is routinely overridden or
    deploys at ROOT. When unsure, prefer the cited contextPath over `""` — dropping a
    real mount is the more common and more damaging error.
- **L2 Module** — from the primer `## Layout`: take the modules whose explanation
  says they serve HTTP endpoints; skip service / library / UI / CLI / test-only.
  Do NOT re-detect module structure here — init-webapp already did. The module dir
  is only *where to look*, never a URL segment (except convention frameworks).
- **L3 Registration root** — the framework's root unit. Read the matching
  reference's **§1 Identify + §2 Structural traversal** to learn what a root is for
  this framework, the grep to find them, and how its prefix composes. Each
  reference's **Dispatch contract** tells you exactly what one worklist entry is and
  what to hand the worker.
- **L4 Handler** — the worker's job; you never read handler bodies here.

**Cross-framework hard rules (apply regardless of framework):**
- **Annotation-framework prefix is the class-level mapping, NOT the package /
  module directory.** A controller in `…/controller/demo/` with
  `@RequestMapping("/demo/form")` serves `/demo/form/…`, not `/demo/demo/form/…`.
  Only convention frameworks (JFinal `AutoBindRoutes`, Struts `@Namespace`) derive a
  prefix from packages.
- **Expect multiple surfaces** — REST + server-rendered UI, annotation + imperative
  code-registered router, admin / public / API modules. Enumerate every surface;
  missing one silently zeroes it. No annotation framework matching means routing is
  imperative, not absent. (GraphQL `/graphql` is a separate enumerator's job, not yours.)
- **Multi-module = grep across all web-surface modules**, not just the one with the
  application entry point (see project-structure.md for Java search strategy).
- **Do NOT skip `example` / `demo` / `sample` modules** that define their own
  controllers — a module like `*-examples-*` / `samples/` with real
  `@RequestMapping`/route handlers is deployable surface and in scope; enumerate
  its controllers too (a result missing them silently drops that whole module).
  **Mount-safe caveat:** include such a module's *own* handlers at their *own*
  routes, but do NOT adopt a demo/test *project's* urlconf that re-mounts the main
  app under a prefix as the mount authority — for path prefixes always use the
  deployed `ROOT_URLCONF` / the handler's own annotation mapping, never a demo
  wrapper's prefix.

### 3b. Build the worklist, then dispatch

For each registration root, build one worklist entry per the reference's Dispatch
contract — recording the already-composed prefix, the root's declaration
`location` (file:line), and the `scope`. Print the worklist as plain text before
dispatching. Then dispatch one worker per entry (§ Dispatch below).

### 4. Dispatch one worker per worklist entry — in parallel when possible

*DO NOT* read controller source files yourself in this phase, and *DO NOT* record anything yourself. Once you have located where a registration root's controllers live (a directory, a glob, or a single file), hand that scope to an `enumerate-http-controllers-worker` sub-agent — via the `Agent` tool with `subagent_type` set to `enumerate-http-controllers-worker` — and the worker reads those files and records each handler. The worker, not you, does the recording; routing every entry through it is what keeps them well-formed.

**This holds even for a single registration root with only a handful of endpoints** — a one-root project still gets exactly one worker; never record them yourself, even if doing so seems quicker. Only what a worker records is collected — anything you record yourself is silently lost, and the whole project scores zero.

**One worklist entry = one worker.** For each entry, dispatch a worker with:

- **framework**: e.g. `spring`, `fastapi` — must match a `references/<lang>/<framework>.md` file.
- **prefix**: the entry's already-composed URL prefix (verbatim from step 3).
- **location**: the entry's `Location` field — file path and line number of this registration root (verbatim from step 3). The worker uses this as its entry point to locate the routing configuration.
- **scope**: the entry's scope — directory, glob, or single file path. This is the controller location the worker reads.

**Dispatch workers in parallel.** When the worklist contains multiple entries whose scopes do not overlap, issue all `Agent` calls in a single message so they run concurrently — concurrent workers record safely without colliding.

**Never dispatch workers with worktree isolation.** Do NOT pass `isolation: "worktree"` (or any isolated-checkout option) on these `Agent` calls. A git worktree is a fresh checkout of tracked files only — it lacks the skill's deployed bundle (its scripts and reference docs are untracked), so a worker placed in one silently records nothing. Dispatch every worker in the main workspace, no isolation.

If two or more entries share files in their scope, group the overlapping entries and dispatch each group serially — wait for the group to finish before dispatching the next. Non-overlapping entries can still run in parallel within or across groups.

Keep a running set of file paths already covered by completed workers. Before dispatching a new worker, check that its scope does not overlap with files already processed.

When all worklist entries are dispatched, move to step 5.

### 5. Finalize and report

Run the deduplication script (removes only byte-identical entries — same endpoint, HTTP method, and region; GET and POST of the same path are kept as distinct entries):

```bash
python scripts/dedup_controllers.py
```

(Run it with no arguments — it deduplicates the workers' recorded entries in place.)

Once the dedup script has run, you are done. Report completion to the user immediately. *DO NOT* try to re-open or re-read the recorded results — what the workers recorded is the source of truth.
