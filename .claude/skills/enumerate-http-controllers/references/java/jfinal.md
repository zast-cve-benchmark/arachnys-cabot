# JFinal Endpoint Enumeration Reference

JFinal is a lightweight Java web framework using convention-over-configuration
routing. Controllers are auto-discovered via package scanning, and method names map
directly to URL paths unless explicitly overridden with annotations. It is a
**convention-routing framework**: the prefix is per-root and known at registration,
so the main agent pre-composes L1 + L3 and hands the whole segment to each worker.

---

## 1. Identify

One grep-able signal each — both agents read this, keep it short.

- **Dependency marker** — `com.jfinal` in `pom.xml` (or the gradle build).
- **Config marker** — a `configRoute(Routes me)` method, on a class that
  `implements JFinalConfig` / `extends <X>Config` (typically in a `config` package).
- **Class marker** — `extends Controller`. Note this catches only *direct*
  subclasses; most projects route through a project-local base class
  (`BaseController`, `AbstractController`, `ApiBase`) that itself extends
  `Controller` — see §3 for the inheritance-chain rule.
- **Annotation / registration markers** — `@Action` (class path), `@ActionKey`
  (method path), `AutoBindRoutes` (package scanner).

```regex
configRoute\s*\(Routes
implements\s+\w*JFinalConfig
extends\s+\w*Config
```

---

## 2. Structural traversal — main agent

The main agent walks the layer checklist and descends to the registration-root
layer; the worker takes over below it. JFinal URLs are constructed from three
layers:

```
{Route Prefix} + {Controller Path} + {Method Path}
```

| Layer | Source | Example |
|-------|--------|---------|
| Route Prefix | `configRoute()` registration | `/admin`, `/api/v1` |
| Controller Path | `@Action` annotation or class name convention | `/cms/content` |
| Method Path | `@ActionKey` or method name | `/query`, `/save` |

The main agent owns the **Route Prefix** layer (L1 + L3); the **Controller Path**
and **Method Path** layers are the worker's (§3).

### L1 Deployment

JFinal's context-path applies before any code, when the web/undertow config
declares one (servlet context-path, undertow mount). If none is declared, the app
mounts at `/` and L1 contributes nothing.

### L3 Registration root

Routes are registered in a `JFinalConfig` implementation class, typically found in
a `config` package:

```java
public void configRoute(Routes me) {
    // Auto-scan with prefix
    me.add(new AutoBindRoutes("/admin", "com.example.admin.controller"));
    me.add(new AutoBindRoutes("/api/v1", "com.example.api.v1"));

    // No prefix (front-end)
    me.add(new AutoBindRoutes("com.example.front.controller"));

    // Manual mapping
    me.add("/hooks", WebhookController.class);
}
```

Each `me.add(...)` call is an independent registration root — either an
`AutoBindRoutes(prefix, package)` scan or a manual `me.add("/x", SomeController.class)`.
Multi-root projects are common (admin / front / api are usually separate). Each root
must be processed with its own prefix in mind.

Because JFinal is a convention framework, the L3 prefix is **the route prefix given
at registration** (plus the convention controller-path layer the worker adds). The
route prefix is known here, at the `me.add` site — so the **main agent pre-composes**
it into the segment handed to the worker, rather than leaving the worker to derive it.

**Locating the config:** Search for the `configRoute` method or classes
implementing / extending `JFinalConfig`:

```regex
configRoute\s*\(Routes
implements\s+\w*JFinalConfig
extends\s+\w*Config
```

### Prefix composition

L1 deployment prefix + L3 route prefix compose into the segment the main agent hands
down; the worker then appends the controller path and method path.

**Illustration** (no context-path → L1 empty): route prefix `/admin` + controller
path `/cms/content` (from `@Action` or the class-name convention) + method `query`
= `/admin/cms/content/query`.

### Enumeration strategy (main-agent steps 1–2)

1. **Find route config** — locate `configRoute()` and list every `me.add(...)` call.
   Each is one registration root with its own prefix (or empty prefix).
2. **For each root, determine its scope** — the scanned package for
   `AutoBindRoutes`, or the single class for `me.add(class)`. That scope, plus the
   pre-composed prefix, is what one worker receives.

(Steps 3–7 — resolving controllers, paths, and methods within a root's scope — are
the worker's; see §3.)

### Dispatch contract
- One worklist entry = one `me.add(...)` registration root in `configRoute()`.
  Multi-root projects (admin / front / api) are the norm — one entry each.
- Hand each worker: `framework=jfinal`,
  `prefix=<L1 deployment + this root's route prefix>` (convention framework → the
  route prefix is known at registration, so pre-compose it; the controller-path and
  method-path layers are the worker's to add),
  `location=<configRoute file:line of this me.add>`,
  `scope=<the AutoBindRoutes scanned package, or the single class for me.add(class)>`.
- Split / merge: one entry per `me.add`; never merge admin / front / api roots
  (different prefixes). A root with no prefix → `prefix=""` (or just the context-path).

---

## 3. Handler enumeration — worker

Given one root's scope and its pre-composed `{root prefix}`, enumerate every routed
handler and compose the final endpoint as
`{root prefix from main} + {controller path} + {method path}`.

### @Action annotation (class-level)

Defines the controller path. Applied to controller classes:

```java
@Action(path = "/system/user", viewPath = "/system/user")
public class SysUserController extends Controller { }

@Action(path = "/cms/content")
public class ContentController extends Controller { }

@Action()  // Root path
public class IndexController extends Controller { }
```

| Attribute | Purpose | Default |
|-----------|---------|---------|
| `path` | URL path for this controller | `"/"` |
| `viewPath` | Template directory | Same as `path` |

The `path` attribute is what matters for endpoint enumeration.

### Convention-based controller path

When a controller class has **no `@Action` annotation**, the path is derived from
the class name:

1. If the class name ends in `Controller`, strip that suffix. If it ends in some
   other suffix (e.g. `Action`), the suffix is **kept** as part of the name.
2. Lowercase the first character.
3. Prefix with `/`.

```java
// No @Action annotation
public class ColumnController extends Controller { }
// → controller path: /column

public class SysMenuController extends Controller { }
// → controller path: /sysMenu

public class LoginAction extends Controller { }
// → controller path: /loginAction  (suffix is NOT "Controller", so it's kept)
```

When `@Action(path = "...")` is present on the class, the annotation's value is used
verbatim and the convention is bypassed entirely. Don't apply both — the annotation
always wins.

### @ActionKey (method-level) — replaces the entire URL

Overrides the default method-name-to-URL mapping. When `@ActionKey` is present, the
method's URL is **exactly** the specified value — it does **not** concatenate with
the controller path or route prefix:

```java
@Action(path = "/")
public class IndexController extends Controller {

    @ActionKey(value = "/admin/login")
    public void login() { }  // Maps to /admin/login (not /login)

    @ActionKey(value = "/admin/dologin")
    public void dologin() { }  // Maps to /admin/dologin

    public void help() { }  // Maps to /help (convention)
}
```

### Convention-based method routing (default)

The rule is **structural, not name-based**: every `public void` instance method
declared on a routed controller class becomes an endpoint. Method name has no
filtering effect — `handler`, `uploadImage`, `doExport`, and `xyz123` are routed
exactly the same way as `index` or `save`. Don't skip methods because the name
"doesn't look like an endpoint".

When a method has no `@ActionKey`, the URL is `{root prefix}{controller-path}/{methodName}`:

```java
@Action(path = "/cms/content")
public class ContentController extends Controller {

    public void query() { }
    // → /admin/cms/content/query

    public void save() { }
    // → /admin/cms/content/save

    public void update() { }
    // → /admin/cms/content/update
}
```

When `@ActionKey("/x")` is present on the method, that value **replaces the entire
URL** — it does not concatenate with the controller path or route prefix (see above).

Methods that are **not** routed:
- Non-public methods (private, protected, package-private).
- Methods with a non-void return type.
- Methods declared on `com.jfinal.core.Controller` itself (framework infrastructure
  like `getPara`, `renderJson`, etc.).

### Inherited methods ARE routed — walk the inheritance chain

**This is the single most common JFinal under-count.** JFinal routes every
`public void` method *visible* on the leaf controller, including ones inherited from
a **project-local base class**.

Many JFinal projects don't have controllers extend `Controller` directly. Instead
they introduce a project-local base class for shared concerns (auth, response
helpers, error handling) and have every controller extend that base. Common names:
`BaseController`, `AbstractController`, `ApiBase`. The base class itself extends
`Controller`. A very common pattern:

```java
public class BaseController extends Controller {   // project base, NOT com.jfinal.core.Controller
    public void index() { }                         // list page
    public void edit() { }
    public void setPageOrderByParams() { }
}
@Action(path = "/cms/column")
public class ColumnController extends BaseController {   // adds its own + inherits the base's
    public void query() { }
}
```

`ColumnController` exposes `/admin/cms/column/{query,index,edit,setPageOrderByParams}` —
the inherited three plus its own. Every controller extending `BaseController` gets the
full inherited set, so these multiply across the admin surface. **Enumerate the
inherited public void methods on every leaf controller, not just the ones it
declares.** Only `com.jfinal.core.Controller`'s own infrastructure methods (above)
are excluded; project base classes in between contribute real endpoints. Skipping
them silently drops one endpoint per base method per controller — frequently the
bulk of a CRUD/admin surface.

A literal grep for `extends Controller` will only match the base class, missing every
actual controller. Build the controller set by transitive closure:

1. Grep for `extends Controller` within the registered package(s). Each hit is either
   an actual controller (extends framework `Controller` directly) or a project-local
   base (e.g. `BaseController extends Controller`).
2. For every hit that looks like a base class — abstract, no `@Action`, named
   `Base*` / `Abstract*` / `*Base` — grep for its subclasses: `extends <BaseName>`.
3. Repeat until no new classes appear. In practice this terminates after one or two
   iterations.

A class participates in routing if `AutoBindRoutes` (or a manual `me.add(...)`)
covers its package and it is non-abstract. Class name suffix doesn't matter —
`*Controller` and `*Action` and any other suffix are all routed if they're in the
registered package. The path-from-class-name convention above handles whatever the
suffix happens to be.

### AutoBindRoutes scanning logic

A custom route scanner that auto-discovers controllers in a package. The main agent
hands the worker the scanned package as `scope`; within it the worker resolves
controllers exactly as above:

```java
// Constructor patterns
new AutoBindRoutes("com.example.controller")             // Scan package, no prefix
new AutoBindRoutes("/admin", "com.example.admin")        // Scan with prefix
new AutoBindRoutes("/admin", "com.example.admin", "Controller")  // Custom suffix
```

1. Find all classes extending `Controller` in the specified package (recursively) —
   via the transitive closure above, not a literal `extends Controller` grep.
2. Check for `@Action` annotation → use `path()` value.
3. No `@Action` → derive path from class name (strip suffix, lowercase first char).

### HTTP method — @ApiMapping or "*"

API controllers may use `@ApiMapping` to constrain HTTP methods:

```java
@Action(path = "/content")
public class ContentApi extends ApiBase {

    @ApiMapping(method = RequestMethod.GET)
    public void get() { }

    @ApiMapping(method = RequestMethod.POST)
    public void save() { }
}
```

Without `@ApiMapping`, all methods accept any HTTP method (method is `"*"`).

### Locating controllers within a root's scope

Regex search patterns:

```regex
# Controller class annotation
@Action\s*\(

# Method-level path override
@ActionKey\s*\(

# API method mapping
@ApiMapping\s*\(

# Direct Controller subclasses (use as a starting point — also expand to project base classes per the inheritance-chain rule above)
extends\s+Controller\b
```

The `extends Controller` pattern only finds direct subclasses. Most real projects
have one or more layers of project-local base classes — see the inheritance-chain
rule above for the transitive-closure approach.

Key files to check:

| Pattern | Purpose |
|---------|---------|
| `**/config/*Config.java` | Route configuration entry (main agent) |
| `**/controller/**/*.java` | Controller classes |
| `**/action/**/*.java` | Action classes (some projects use this convention) |
| `**/api/**/*.java` | API endpoint classes |
| `**/route/AutoBindRoutes.java` | Custom auto-binding logic |

### Per-handler steps (worker steps 3–7)

3. **Identify controller classes via transitive closure** — see the inheritance-chain
   rule. Don't rely solely on `extends Controller`.
4. **Resolve the controller path** — `@Action` annotation if present, otherwise
   derive from class name. Don't assume the class name ends in `Controller`.
5. **Enumerate methods** — every `public void` method on the class is an endpoint
   (incl. inherited ones). Apply the rule, not name heuristics.
6. **Compose the URL** — `{root prefix} + {controller path} + {method path}`. The
   root prefix is the part most easily forgotten when zoomed in on a single file;
   bring it from the worklist, not from memory.
7. **Determine HTTP method** — `@ApiMapping` if present, otherwise `"*"`.

(Real-world projects commonly show this multi-root + project-local-`BaseController`
shape illustrated above.)
