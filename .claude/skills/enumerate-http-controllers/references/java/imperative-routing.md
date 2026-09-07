# Imperative / No-Annotation HTTP Routing Reference (Java)

Most Java web frameworks declare routes **declaratively** — annotations
(`@RestController`, `@Path`, `@WebServlet`) or convention/config files
(Struts `struts.xml`, Play `conf/routes`). The other half of the world wires
routes **imperatively**: handler objects are registered onto a router/dispatcher
by ordinary method calls at startup. A grep for annotations finds **nothing** in
these projects — but they absolutely still serve HTTP endpoints. This is the Java
analogue of Go's [net/http](../go/nethttp.md) reference.

Routing here is **per-root, pre-composed by the main agent**: each registration
root binds a prefix to a handler list, so the main agent composes L1 + the
version/mount segment and hands the whole prefix down; the worker enumerates that
root's handler list and resolves each handler's path from where it actually lives.

---

## 1. Identify

A grep for the annotation/convention frameworks finds **nothing** — no
`@RestController`/`@Path`/`@WebServlet`/`@Action`, no `struts.xml`/`conf/routes`.
That absence is the signal: routing is imperative, **not** absent. Confirm with
the imperative markers:

- **Server bootstrap** — `ServerBootstrap`, `createHttpServer`, `Undertow.builder`,
  `Javalin.create`, `Spark.port`, `RouterFunctions`, `Handlers.routing`,
  `new \w*Router`.
- **Spec-object indirection** (the Netty-internal-REST shape — Flink/Hadoop/Spark) —
  `initializeHandlers`, `RestHandlerSpecification`, `getTargetRestEndpointURL`,
  `getHttpMethod`.

This family includes Vert.x Web (`router.get("/x").handler(h)`), Undertow
(`Handlers.routing().get("/x", h)`), Spark Java / Javalin / Ratpack
(`get("/x", h)`), Spring WebFlux functional (`RouterFunctions.route().GET(...)...build()`),
raw Netty + a Router (a `ChannelInboundHandler` per route, path/method on a
spec object — §3.3), and bespoke front-handler dispatchers that `switch` on
`request.uri()`. You will not have a per-library reference for every one — they
share **one discovery technique**. Learn the technique, not the library.

---

## 2. Structural traversal — main agent

The main agent finds the server bootstrap, lists the registration roots, and
composes the prefix prepended at registration. It stops there — it does **not**
read handlers or spec objects (that is the worker's job, §3).

**Find the HTTP server bootstrap.** Where does the process bind a port / build
the router or dispatcher?

```bash
# Server bootstrap (where the router/dispatcher is created)
grep -rnE 'ServerBootstrap|createHttpServer|Undertow\.builder|Javalin\.create|RouterFunctions|Handlers\.routing|new\s+\w*Router' --include='*.java' .
```

**Find the registration root(s).** A registration root is the method or block
where handlers are added to that router — often one central method (an
`initializeHandlers()` / `setupRoutes()` / a `RouterFunctions.route()...build()`
chain). There may be several roots (admin vs API). These greps are
library-agnostic; run them across the project (or the bootstrap module) and
follow what hits:

```bash
# Imperative route registration (verb-named methods on a router/app/group)
grep -rnE '\.(get|post|put|delete|patch|head|options|route|add|addPrefixPath|addExactPath|handle|GET|POST|PUT|DELETE)\s*\(' --include='*.java' .

# Spec-object indirection (§3.3): method/url getters and handler-list builders
grep -rnE 'getTargetRestEndpointURL|getHttpMethod|initializeHandlers|getUrl\(\)|getPath\(\)|getMethod\(\)' --include='*.java' .

# Front-handler dispatch (§3.2): branching on path/method inside a handler
grep -rnE 'getRequestURI|request\(\)\.path|request\(\)\.method|\.uri\(\)' --include='*.java' .
```

Inline routers light up the first; spec-object internal-REST layers light up the
second; bespoke dispatchers light up the third.

**Compose the prefix/version prepended at registration.** Imperative routers
frequently prepend a base path or API version **at registration time**, so the
path on the spec/call-site is not the full URL. Read the registration root for
any literal/constant prepended to the path (a version like `/v1`, a mount prefix
like `/api`) and prepend it to the whole root's handler list:

```java
// A version segment prepended for every supported version:
for (Version v : handler.getSupportedVersions()) {
    register(router, "/" + v + handler.getUrl(), handler.getMethod(), handler);
    // "/v1" + "/jobs/:jobid/config" -> /v1/jobs/:jobid/config
}

// A mount prefix:
pathHandler.addPrefixPath("/api", apiRoutingHandler);   // every route under /api
```

If a root registers its handlers under multiple versions, that becomes one
endpoint per version downstream (`/v1/...` and `/v2/...` are distinct) — but the
main agent just hands the version/mount segment; the worker fans it out per
handler.

### Dispatch contract
- One worklist entry = one registration root (one `initializeHandlers()` /
  `RouterFunctions.route()...build()` / route-registration block). One worker takes
  the WHOLE handler list of that root (it greps the root first to avoid tail-drop —
  see §3).
- Hand each worker: `framework=imperative-routing`,
  `prefix=<L1 deployment + any version/mount segment prepended at registration>`
  (e.g. `/v1`, `/api`), `location=<the registration-root method, file:line>`,
  `scope=<the registration-root file PLUS the messages/handlers dir(s) it
  references — the worker needs the spec classes to resolve URLs>`.
- Split / merge: one entry per registration root. If a single root registers
  handlers contributed from several modules/packages, give each module its own
  entry. Do NOT over-split one module's handler list into many tiny scopes.

---

## 3. Handler enumeration — worker

Given one registration root's scope, enumerate every routed handler and compose
the final endpoint (apply the prefix the main agent handed you). The path and
method are **not always at the call site** — there are three forms. Identify
which one the root uses before enumerating.

### 3.1 At the call site (inline) — easiest

The path string and HTTP method are literals right at the registration call.

```java
// Vert.x Web
Router router = Router.router(vertx);
router.get("/api/users").handler(this::listUsers);          // GET  /api/users
router.post("/api/users").handler(this::createUser);        // POST /api/users
router.route("/api/health").handler(this::health);          // *    /api/health (no method = all)

// Undertow
RoutingHandler routes = Handlers.routing()
    .get("/users/{id}", getUser)                            // GET  /users/{id}
    .post("/users", createUser)                             // POST /users
    .add("PUT", "/users/{id}", updateUser);                 // PUT  /users/{id}

// Spark Java / Javalin (static or instance style)
get("/ping", (req, res) -> "pong");                         // GET  /ping
app.post("/login", loginHandler);                           // POST /login

// Spring WebFlux functional
RouterFunction<ServerResponse> routes = RouterFunctions.route()
    .GET("/api/items", itemHandler::all)                    // GET  /api/items
    .POST("/api/items", itemHandler::create)                // POST /api/items
    .build();
```

**Enumeration rule:** the method is the verb in the call
(`get`/`post`/`put`/`delete`/`patch`/`GET`/`POST`/…); a verb-less `route(...)` /
`use(...)` / `path(...)` that takes any method → record method `"*"`. The path is
the literal argument. Record one endpoint per call. For the `region`, follow the
handler passed in (lambda body, or the method/class behind a method-reference) and
anchor on its body — see §3.4.

### 3.2 Branched inside one front handler

A single handler is registered for a prefix (or `/`), and it branches on the
request internally:

```java
router.route("/api/*").handler(this::dispatch);

void dispatch(RoutingContext ctx) {
    switch (ctx.request().path()) {
        case "/api/users":  handleUsers(ctx);  break;   // endpoint /api/users
        case "/api/orders": handleOrders(ctx); break;   // endpoint /api/orders
    }
    if (ctx.request().method() == HttpMethod.POST) { ... }   // method branch
}
```

**Enumeration rule:** record **one endpoint per branch** — read the `switch`/`if`
on `path()`/`getRequestURI()` for paths and the branch on `method()` for methods.
A handler that does not branch on method → method `"*"`.

### 3.3 In a metadata/spec object the handler carries (indirection)

The registration loop is generic — it adds `(spec, handler)` pairs — and the path
and method are **getters on the spec object**, not literals at the call site.
This is the shape used by Netty-based internal REST layers (Flink, Hadoop YARN,
Spark, etc.).

```java
// Registration root: a generic loop, no literal paths here.
for (Tuple2<HandlerSpec, Handler> h : initializeHandlers()) {
    router.addHandler(h.spec.getUrl(), h.spec.getMethod(), h.handler);
}

// initializeHandlers() builds handler+spec pairs:
handlers.add(new JobConfigHandler(..., JobConfigHeaders.getInstance()));

// The spec object is where path & method live:
class JobConfigHeaders implements HandlerSpec {
    public String getUrl()    { return "/jobs/:jobid/config"; }   // <- the path
    public HttpMethod getMethod() { return GET; }                 // <- the method
}
```

> **Worked example — Apache Flink.** The registration root is a
> `RestServerEndpoint` subclass's `initializeHandlers()` returning
> `List<Tuple2<RestHandlerSpecification, ChannelInboundHandler>>`. Each handler is
> constructed with a `MessageHeaders` (a `RestHandlerSpecification`) singleton.
> The endpoint comes from `getTargetRestEndpointURL()` (e.g. `/jobs/:jobid/config`)
> and the method from `getHttpMethod()`. Flink is one instance of this form — the
> *technique* (find the registration loop → follow each handler to its spec
> object → read the URL/method getters) is what generalizes.

**Enumeration rule:** do not try to read paths at the registration loop — it has
none.

**First, build the complete handler inventory — do NOT rely on reading the long
registration method top-to-bottom and remembering every entry.** The registration
method (`initializeHandlers()` etc.) is often hundreds of lines, with the
`handlers.add(...)` calls split across **several blocks**; reading it linearly and
recalling each one is exactly how a weak model drops the tail. Instead, grep the
registration root for every handler construction and count them, then work the
list to exhaustion:

```bash
# Every handler added in the registration root file — your worklist, with a count.
grep -nE 'handlers\.add|\.add\(new |new \w+Handler|Headers\.(getInstance|INSTANCE)' \
  <registration-root.java>
```

Enumerate **every** entry the grep returns. Before you finish, your recorded
count must equal the number of handlers the root registers (self-check (c) below).
If the root adds 60 handlers, you record ~60 — not the 40 you happened to read
before the method scrolled off.

For each handler added in the registration root:

1. Open the **spec/metadata type** it is constructed with; read the path getter
   (`getUrl()`/`getPath()`/`getTargetRestEndpointURL()`) and the method getter
   (`getMethod()`/`getHttpMethod()` → an HTTP-method enum/constant). The **path and
   method come from the spec.**

   **The URL is whatever the getter actually returns — read it, never infer it
   from the handler or spec class name.** `ShutdownHandler` is not `/shutdown`; its
   `ShutdownHeaders.getTargetRestEndpointURL()` returns `/cluster`. Open the file
   and read the value. A path guessed from a class name is a wrong endpoint (a
   simultaneous miss of the real one and a false positive).

   **Resolve non-literal URL constants — do not approximate them.** The getter
   frequently returns a `URL` constant that is *computed*, not a bare string
   literal. You must follow the construction and resolve it exactly:
   - `return "/jobs/:" + JobIDPathParameter.KEY + "/execution-result";` →
     read `KEY` (it is `jobid`) → `/jobs/:jobid/execution-result`.
   - `URL = String.format("/jobs/%s/savepoints", JobIDPathParameter.KEY);` →
     substitute each `%s` with its `KEY` → `/jobs/:jobid/savepoints` (do **not**
     invent extra segments like `/jm/`).
   - `URL = ClusterDataSetListHeaders.URL + "/:" + ClusterDataSetIdPathParameter.KEY;`
     → open the referenced `ClusterDataSetListHeaders.URL` (`/datasets`) and
     concatenate → `/datasets/:datasetid`. Read the referenced constant; don't
     guess its value or its position in the path.

   When a constant references another class's constant or a `*PathParameter.KEY`,
   `Read`/`Grep` that definition and substitute the real value. Recording the
   unresolved template (`URL`, `%s`) or a guessed path both produce a wrong endpoint.

   **Mechanical extraction — surface every real URL string before you record, so
   you cannot guess.** Do NOT build a list of `(handler → url)` from the handler
   class *names* (that is guessing: `RescalingTriggerHandler` is **not**
   `/rescale` — its `RescalingTriggerHeaders` declares `/jobs/:jobid/rescaling`).
   Instead, dump the actual URL declarations from the spec classes in one shot and
   read the literals out of the output:

   ```bash
   # Every spec class's declared URL + method — the source of truth, not the name.
   grep -rEn 'String URL =|getTargetRestEndpointURL|getHttpMethod|HttpMethodWrapper' \
     <messages-dir>   # e.g. the rest/messages/ tree holding the *Headers classes
   ```

   Then, for any `URL` that is a computed constant (`String.format`, `A.URL + …`),
   open that one class and resolve it as above. **Every URL you record must be a
   string you actually saw in a `grep`/`Read` output** — if you typed a path that
   never appeared in tool output, you guessed it; delete it and go read the getter.

   **Self-verify EVERY recorded path before finishing — this catches the #1 error.**
   For each endpoint, grep the source for the distinctive literal segment of its
   path (the action word, usually the last segment — `rescaling`, `savepoint-disposal`,
   `thread-dump`, `execution-result`):

   ```bash
   grep -rn 'rescaling' <messages-dir>   # the EXACT word you recorded must appear verbatim
   ```

   **Transcribe each path segment character-for-character from the grep/Read output
   — never retype it from the spec/handler class name or from memory.** The recurring
   failure is a one-character corruption of a value that WAS already in your tool
   output: `rescaling`→`rescale` (truncated), `logs`→`log` (singularized),
   `thread-dump`→`thread` (truncated), `coordinators`→`coordination` (wrong word),
   `savepoint-disposal` dropped for an unrelated `/savepoints/...`. If your recorded
   segment is not found verbatim — or grep shows a *different* spelling than what you
   recorded — the path is corrupted: overwrite it with the exact characters from the
   grep line. A path off by one character is a wrong endpoint (a simultaneous miss +
   false positive), so this check is not optional.
2. Open the **handler class** itself and record the `region` at its
   request-processing method body (§3.4). The spec gives you path+method; the
   handler class gives you the `region`. **Never** record the region on the
   registration loop line or on the spec class.

To find the pair fast: once you know the spec interface name (the type returned by
the registration loop), grep for its implementations to read the path/method
getters, and open the **paired handler class** for the region.

### 3.4 `region` — anchor at the handler body, never the registration site

Across all three forms, the `region` you record must point at **where the request
is actually handled** — the handler's processing-method body — not at the line
that registers the route. The registration root is only your *discovery anchor*:
once you have paired `(path, method, handler)`, follow the handler to its code and
record the region there. Downstream auditing reads the source at `region` to find
vulnerabilities, so a region on a `new XxxHandler(...)` construction line points
the auditor at plumbing, not logic.

The handler's processing method, by form:

- **Inline lambda** (`router.get("/x").handler(ctx -> { ... })`) → the lambda body
  *is* the handler and lives at the registration site; recording there is correct
  **only because the body is there.**
- **Inline method-reference / named handler** (`.handler(this::listUsers)`,
  `.get("/x", getUser)`) → open `listUsers` / the `getUser` handler and record its
  method body, not the `.get(...)` line.
- **Branched front-handler (§3.2)** → the `case` body, or the method it delegates to.
- **Spec-object (§3.3)** → the handler class's request-processing method: usually
  the override of the framework's handler interface — commonly `handleRequest`,
  `respondToRequest`, `channelRead0`, `service`, `doGet`/`doPost`, or `handle`. If
  the concrete handler only inherits it and adds no override, record the concrete
  class's narrowest response-producing member; do **not** record the abstract base
  shared by every handler (that collapses every endpoint onto one file too).

**Which two line numbers:** `start_line` = the **signature line of that
request-handling method** (e.g. the `protected ... handleRequest(...)` line),
`end_line` = that method's **closing brace**. Record the method's **span**, not a
single line — and **always provide `end_line`** (the auditor reads the whole span;
a one-line region starves it). Do **not** use the class-declaration line
(`public class XxxHandler extends ...`) as `start_line` — that is the class header,
not the handler logic. If the request method is genuinely absent (inherit-only),
span the concrete class body instead, but prefer the method every time it exists.

❌ Wrong — region on the registration line: `/jobs/:jobid/config` → `WebMonitorEndpoint.java:258` (the `new JobConfigHandler(...)` call).
❌ Wrong — region on the class-declaration line, no `end_line`: `/jobs/:jobid/config` → `JobConfigHandler.java:46` (the `public class JobConfigHandler` header).
✅ Right — region spans the handler's processing method: `/jobs/:jobid/config` → `JobConfigHandler.java:66-69` (the `handleRequest(...) { ... }` body).

**Coverage outranks region precision.** Recording *every* endpoint matters more
than a tight region on each. If a registration root lists many handlers and
finding each method span is slowing you down, do **not** drop endpoints to keep up
— record the endpoint with a coarser region (the handler class's first line) and
move on. A missed endpoint is never audited at all; a coarse region is still
audited (the snippet is LSP-completed downstream). Never trade an endpoint for a
tighter region.

**Self-checks before finishing:** (a) if **most of your regions share one file**
(typically the registration-root file), you anchored at the registration site —
go back and follow each handler to its own class. (b) if **most regions have no
`end_line`, or `start_line` sits on a `public class ...` line**, you anchored at
the class header instead of the request method — re-point them at the method span.
(c) compare your recorded count against the number of handlers registered in the
root — if the root adds 60 handlers and you recorded 40, you dropped the tail;
go back for the rest.

### 3.5 Compose the prefix/version onto every path

The main agent handed you the prefix prepended at registration (a version like
`/v1`, a mount prefix like `/api`). Compose it onto every endpoint from this root,
and record the **already-composed** full path, per SKILL.md step 3. If a handler
is registered under multiple versions, record one endpoint per version
(`/v1/...` and `/v2/...` are distinct entries).

### 3.6 Path-parameter syntax

Imperative routers use varied placeholder syntaxes. Record the path **as written**
(the auditor matches on the registered template, not a normalized form):

| Syntax | Example | Seen in |
|--------|---------|---------|
| `:name` | `/jobs/:jobid` | Netty routers (Flink), Sinatra-style |
| `{name}` | `/users/{id}` | Undertow, Spring, Vert.x (also supports `:name`) |
| `*` / `/*` | `/static/*`, `/api/*` | prefix / catch-all |
| `{name...}` / `*name` | `/files/{path...}` | multi-segment trailing wildcard |

### 3.7 Enumeration checklist

- **No annotations found ≠ no endpoints.** It means routing is imperative — work
  the registration root the main agent handed you.
- **Identify the form first (§3):** inline literals, branched front-handler, or
  spec-object indirection. The form decides where you read path & method from.
- **Inline** → method = the verb in the call, path = the literal argument, one
  endpoint per call.
- **Branched front-handler** → one endpoint per `path()`/`uri()` branch; method
  from the `method()` branch, else `"*"`.
- **Spec-object** → path & method from the handler's spec/metadata type (URL getter
  + method getter); the `region` from the **handler class's** request-processing
  method, not the spec and not the registration loop. **Build the handler inventory
  by grepping the registration root first** (count them, enumerate every one — don't
  read the long method linearly and drop the tail). **Read the URL getter's actual
  return value and resolve any computed constant** (`String.format`, `OTHER.URL + …`,
  `*PathParameter.KEY`) — never infer the path from the handler/spec class name.
- **`region` = the request-handling method's span, never the registration site or
  the class header (§3.4).** `start_line` = the method signature line, `end_line` =
  its closing brace — always provide `end_line`. If most regions land in one file,
  or sit on `public class ...` lines, or lack `end_line`, you anchored wrong.
- **Compose the prefix/version** prepended at registration time onto every path.
- **Record the path as written** (`:id`, `{id}`, `*`) — do not normalize.
- A verb-less / method-agnostic registration (`route`, `use`, `addPrefixPath`) →
  method `"*"`.
