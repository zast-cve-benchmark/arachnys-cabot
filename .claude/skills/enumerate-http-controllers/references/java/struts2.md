# Struts2 Endpoint Enumeration Reference

Apache Struts2 uses action-based routing. Routes are defined via XML configuration
(`struts.xml`), annotations (Convention Plugin), or convention-over-configuration.
Each action maps to a URL path and executes a method on an action class. It is a
**convention-routing framework**: the namespace is the prefix and is known at the
package/annotation, so the main agent pre-composes L1 + namespace and hands the whole
segment to each worker.

---

## 1. Identify

One grep-able signal each — both agents read this, keep it short.

- **Dependency marker** — `struts2-core` in `pom.xml` (or the gradle build).
- **Config marker** — a `struts.xml` (and `struts-*.xml`) with
  `<package namespace="/x">` / `<action>` blocks.
- **Annotation markers (Convention Plugin)** — `@Namespace` (class path),
  `@Action` (method/class path), `@Result` (result mapping).
- **Class marker** — `extends ActionSupport`. Note this catches only *direct*
  subclasses; most projects route through a project-local base class
  (`BaseAction`, `AbstractAction`) that itself extends `ActionSupport` — see §2/§3
  for the inheritance-chain rule.

```regex
<action\s+name=
@Namespace\s*\(
@Action\s*\(
extends\s+ActionSupport\b
struts\.convention\.action\.packages
```

---

## 2. Structural traversal — main agent

The main agent walks the layer checklist and descends to the registration-root
layer; the worker takes over below it.

### L1 Deployment

The context path plus any Struts filter mapping applies before any code. Combine the
servlet/web context-path with the Struts dispatcher filter's `url-pattern` (the
filter mapping). If neither narrows the mount, the app mounts at `/` and L1
contributes nothing.

### L3 Registration root

A root is one **namespace**, sourced one of two ways — preserve the distinction:

- **struts.xml** — each `<package namespace="/x">` block is a root; its
  `<action name=...>` children are the actions in scope.
- **Convention Plugin** — each `@Namespace`-annotated action class is a root (or,
  without `@Namespace`, the package path determines the namespace).

```xml
<struts>
    <package name="default" namespace="/" extends="struts-default">
        <action name="hello" class="com.example.HelloAction" method="execute">
            <result name="success">/hello.jsp</result>
        </action>
    </package>

    <package name="admin" namespace="/admin" extends="struts-default">
        <action name="users" class="com.example.UserAction" method="list">
            <result name="success">/admin/users.jsp</result>
        </action>
        <action name="userSave" class="com.example.UserAction" method="save">
            <result name="success" type="redirect">users</result>
        </action>
    </package>
</struts>
```

The Convention Plugin auto-discovers action classes; it is enabled either by the
`struts.convention.action.packages` constant in `struts.xml` or by the
`struts2-convention-plugin` dependency:

```xml
<constant name="struts.convention.action.packages" value="com.example.actions"/>
```

```java
@Namespace("/admin")
public class UserAction extends ActionSupport {
    // All actions in this class are under /admin/*
}
```

Without `@Namespace`, the package path (under the configured `actions` root)
determines the namespace:

| Package | Namespace |
|---------|-----------|
| `com.example.actions` | `/` |
| `com.example.actions.admin` | `/admin` |
| `com.example.actions.api.v1` | `/api/v1` |

### Prefix composition

Struts2 is a **convention framework → the namespace IS the prefix, known at the
package/annotation, so the main agent pre-composes L1 + namespace** and hands the
whole segment to the worker (the worker appends only each action name).

**Illustration** (no extra context-path → L1 empty): namespace `/admin` +
action name `users` = `/admin/users.action` — the main agent composes `/admin` and
the worker appends `users` and the `.action` suffix.

### Enumeration strategy (main-agent steps 1–2)

1. **Find every registration root** — XML `<package namespace="...">` blocks and
   Convention Plugin namespaces (`@Namespace` classes, or package-derived
   namespaces under the configured `actions` root). Each is one worklist entry with
   its own namespace prefix.
2. **For each root, list the action classes / config in scope** — via XML
   `<action>` entries, or by transitive closure of `extends ActionSupport` (§3)
   within the convention package. That scope, plus the pre-composed prefix, is what
   one worker receives.

(Steps 3+ — resolving action names, methods, and HTTP verbs within a root's scope —
are the worker's; see §3.)

### Dispatch contract

- One worklist entry = one `<package namespace>` (struts.xml) **or** one
  `@Namespace` group (Convention Plugin).
- Hand each worker: `framework=struts2`,
  `prefix=<pre-composed L1 deployment + this root's namespace>` (convention framework
  → the namespace is known at the package/annotation, so pre-compose it; only the
  action name is the worker's to add),
  `location=<struts.xml package line, or a representative action class file:line>`,
  `scope=<the action classes / config for that namespace>`.
- Split / merge: one entry per namespace; don't merge namespaces (different
  prefixes). A namespace `/` → `prefix=""` (or just the context-path).

---

## 3. Handler enumeration — worker

Given one root's scope and its pre-composed `{namespace}` prefix, enumerate every
routed action and compose the final endpoint as
`{namespace}/{actionName}[.action|.do]`.

### XML actions

Each `<action name="x">` under the package is one endpoint at `namespace/x` (with
the `.action`/`.do` suffix). Its attributes:

| Attribute | Purpose | Default |
|-----------|---------|---------|
| `name` | URL path segment (after namespace) | Required |
| `class` | Fully qualified action class | Optional (default to action) |
| `method` | Method to invoke on action class | `"execute"` |

The `method` attribute names the handler/region — the invoked method on the action
class (default `execute()`).

**Wildcard mappings** expand one `<action>` into many via `{1}`:

```xml
<action name="*User" class="com.example.UserAction" method="{1}">
    <result>/user/{1}.jsp</result>
</action>
<!-- /listUser → UserAction.list() -->
<!-- /editUser → UserAction.edit() -->
```

### Convention Plugin — `@Action` (method-level)

`@Action("name")` on a method maps it to `{namespace}/name`:

```java
@Namespace("/admin")
public class UserAction extends ActionSupport {

    @Action("users")
    public String list() { return "success"; }   // → /admin/users

    @Action("user-save")
    public String save() { return "success"; }    // → /admin/user-save
}
```

`@Actions` maps one method to multiple action names:

```java
@Actions({
    @Action("list"),
    @Action("list-all")
})
public String list() { return "success"; }
// → /admin/list AND /admin/list-all
```

`@Result` declares result mappings; it does not add an endpoint:

```java
@Action(value = "users", results = {
    @Result(name = "success", location = "/users.jsp"),
    @Result(name = "error", location = "/error.jsp")
})
public String list() { return "success"; }
```

### Convention Plugin — no annotations

When no annotations are present, action name and method are derived by convention.

**Class name → action name:**

| Class Name | Action Name | URL |
|------------|-------------|-----|
| `UserAction` | `user` | `/user` |
| `ListUsersAction` | `list-users` | `/list-users` |
| `AdminPanelAction` | `admin-panel` | `/admin-panel` |

Rules: remove `Action` suffix, convert CamelCase to hyphen-case, lowercase.

**Method → action:** by default the `execute()` method is called. With DMI (Dynamic
Method Invocation) enabled, other methods are reachable via `!`:

```java
public class UserAction extends ActionSupport {
    public String execute() { }  // → /user
    public String list() { }     // → /user!list (DMI)
    public String save() { }     // → /user!save (DMI)
}
```

The `execute()` / action method is the handler/region.

### The `.action` suffix convention

Composed endpoints carry the Struts suffix: `{namespace}/{actionName}.action` (or
`.do`). Example: namespace `/admin` + action `users` = `/admin/users.action`.

### REST Plugin

The REST plugin maps HTTP methods to CRUD action methods (dependency
`struts2-rest-plugin`):

```java
@Namespace("/api/users")
public class UsersController extends ActionSupport {
    public String index()   { return "success"; }  // GET    /api/users
    public String show()    { return "success"; }  // GET    /api/users/{id}
    public String create()  { return "success"; }  // POST   /api/users
    public String update()  { return "success"; }  // PUT    /api/users/{id}
    public String destroy() { return "success"; }  // DELETE /api/users/{id}
}
```

| HTTP Method | Action Method | Typical URL |
|-------------|---------------|-------------|
| GET | `index()` | `/api/users` |
| GET | `show()` | `/api/users/{id}` |
| POST | `create()` | `/api/users` |
| PUT | `update()` | `/api/users/{id}` |
| DELETE | `destroy()` | `/api/users/{id}` |

Without the REST plugin, an action's HTTP method is `"*"` (a form submit accepts any
verb).

### Actions via a project-local base class — walk the inheritance chain

Most Struts2 projects centralize cross-cutting concerns (auth, validation, locale,
response helpers) on a shared base class. Typical names: `BaseAction`,
`AbstractAction`. Subclasses inherit `extends ActionSupport` *transitively*, not
directly. A literal grep for `extends ActionSupport` will only catch the base class
itself, not the dozens of real action classes underneath it.

Build the action set by transitive closure:

1. Grep for `extends ActionSupport` (and `implements Action`) inside the configured
   action packages. Each hit is either a real action or a project-local base.
2. For each base candidate (often abstract, often named `Base*` / `Abstract*`), grep
   for its subclasses (`extends <BaseName>`).
3. Repeat until no new classes appear. In practice this terminates in one or two
   iterations.

If the project uses the Convention Plugin, this matters somewhat less because the
plugin auto-discovers any class in `struts.convention.action.packages`. But you still
need the closure to know which discovered classes count as actions vs. utility
classes that happen to live in the same package.

When composing URLs, walk up the inheritance chain to inherit any `@Namespace` from
the base class.

### Locating actions within a root's scope

```regex
# XML configuration
<action\s+name=

# Annotation-based
@Namespace\s*\(
@Action\s*[\(\(]
@Actions\s*\(

# Direct ActionSupport subclasses (use as a starting point — also expand to project base classes per the inheritance-chain rule above)
extends\s+ActionSupport\b
extends\s+Action\b
implements\s+Action\b

# Package configuration
struts\.convention\.action\.packages

# REST plugin
extends\s+\w*RestAction\w*
```

The `extends ActionSupport` pattern only finds direct subclasses. Most real projects
have one or more layers of project-local base classes — see the inheritance-chain
rule above.

Key files to check:

| File/Pattern | Purpose |
|--------------|---------|
| `src/main/resources/struts.xml` | Primary route configuration |
| `src/main/resources/struts-*.xml` | Additional config files |
| `**/action/**/*.java` | Action classes (convention) |
| `**/actions/**/*.java` | Action classes (convention) |
| `**/controller/**/*.java` | Controller classes |
| `pom.xml` / `build.gradle` | Check for Convention/REST plugin |

### Per-handler steps (worker steps 3+)

3. **Identify action classes via transitive closure** — see the inheritance-chain
   rule. Don't rely solely on `extends ActionSupport`.
4. **Resolve URL from XML** — `namespace` + action `name`.
5. **Resolve URL from annotations** — `@Namespace` (walking up to base classes if
   needed) + `@Action` value.
6. **Resolve URL from convention** — package path to namespace, class name
   (CamelCase → hyphen-case, drop `Action` suffix) to action name; method via
   `execute()` / DMI. Apply the `.action`/`.do` suffix.
7. **Determine HTTP method** — REST plugin maps method names to HTTP verbs;
   otherwise `"*"` (form submit accepts any).
