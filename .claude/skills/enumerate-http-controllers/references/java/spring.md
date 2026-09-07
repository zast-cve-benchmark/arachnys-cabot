# Spring Boot Endpoint Enumeration Reference

Spring is a **per-class-prefix annotation** framework: each `@Controller` /
`@RestController` class is a registration root carrying its own class-level
`@RequestMapping` prefix; the method mapping appends to it. The main agent finds the
roots and hands the worker only the deployment (L1) prefix; the worker composes each
class's own prefix itself. This file is split so the main agent reads §1–§2 and the
worker reads §1 + §3.

---

## 1. Identify

One grep-able signal per layer confirms Spring MVC / Spring Boot:

- **Dependency marker** (pom/gradle): `spring-boot-starter-web` or `spring-webmvc`.
- **Class marker**: `@RestController`, `@Controller`, or `@SpringBootApplication`.
- **Mapping marker**: `@GetMapping` / `@PostMapping` / `@RequestMapping` (and the
  other HTTP-verb variants) on methods.

---

## 2. Structural traversal — main agent

Walk the layer checklist for Spring, descend to the registration-root layer, and
dispatch a worker below it. (Worker: skip to §3.)

### L1 Deployment

The deployment prefix is `server.servlet.context-path` in
`application.properties` / `application.yml` (`server.servlet.context-path=/app`).
Absent → the app mounts at `/`. In a multi-module app **each web module may declare
its own** `application.*`, so read the config of every web-surface module, not just
the entry-point module's.

### L3 Registration root

Each `@RestController` / `@Controller` class is a registration root; its class-level
`@RequestMapping` is that root's prefix. Find the roots across **all** web modules —
controllers may live in any module on the classpath, not just the one holding
`@SpringBootApplication`:

```bash
grep -rl '@RestController\|@Controller' --include='*.java' .
```

This finds them regardless of package naming (`controller`, `api`, `rest`,
`resource`, or project-specific). A literal grep misses two indirection patterns —
**meta-annotations** (a custom `@interface` that itself carries `@RestController`)
and **abstract base classes** (routing annotations inherited by subclasses). They
exist; the full transitive-closure rule for them lives in §3 (it is the worker's to
resolve when composing each class's prefix).

### Prefix composition

```
endpoint = context-path (L1) + class @RequestMapping (L3) + method mapping (L4)
```

The package / directory / module is **never** a URL prefix — Spring derives nothing
from packages (unlike Struts `@Namespace` or JFinal `AutoBindRoutes`). Because one
worker scope holds several controller classes that do not share a class prefix, the
main agent hands only the **L1** segment; each class's L3 prefix is the worker's to
compose.

### Dispatch contract
- One worklist entry = one controller **package / directory** within a web-surface
  module (e.g. one `…/controller/` dir), NOT one entry per `@Controller` class —
  grouping classes under one worker avoids worker explosion on large apps.
- Hand each worker: `framework=spring`, `prefix=<this module's context-path, or "">`
  (L1 ONLY — the per-class `@RequestMapping` is the worker's to compose),
  `location=<the controller package dir, or a representative controller file:1>`,
  `scope=<the package dir glob, e.g. <module>/src/main/java/**/controller/**>`.
- Split / merge: one entry per controller package per web module. Do NOT split a
  package into per-class entries; do NOT merge two modules whose context-paths
  differ. A module with controllers in several packages → one entry per package.

---

## 3. Handler enumeration — worker

Given one controller package's scope, enumerate every routed method. (Main agent:
you already did §2; skip to your next root.) At endpoint-composition time apply the
main agent's **L1** prefix + **this class's own** `@RequestMapping` + the method
mapping — the package directory is never a prefix.

### 3.1 Core mapping annotations

All mapping annotations derive from `@RequestMapping`:

| Annotation | HTTP Method | Description |
|------------|-------------|-------------|
| `@RequestMapping` | Any | Generic mapping |
| `@GetMapping` | GET | Retrieve resources |
| `@PostMapping` | POST | Create resources |
| `@PutMapping` | PUT | Replace resources |
| `@DeleteMapping` | DELETE | Delete resources |
| `@PatchMapping` | PATCH | Partial update |

#### Class-level and method-level mapping

```java
@RestController
@RequestMapping("/api/users")  // Class-level prefix
public class UserController {

    @GetMapping("/{id}")  // GET /api/users/{id}
    public User getUser(@PathVariable Long id) { ... }

    @PostMapping  // POST /api/users
    public User createUser(@RequestBody User user) { ... }

    @PutMapping("/{id}")  // PUT /api/users/{id}
    public User updateUser(@PathVariable Long id, @RequestBody User user) { ... }

    @DeleteMapping("/{id}")  // DELETE /api/users/{id}
    public void deleteUser(@PathVariable Long id) { ... }
}
```

> **URL = L1 context-path + class `@RequestMapping` + method mapping, nothing else.**
> The package / directory / module is **not** a URL prefix — never prepend it. A
> controller in `…controller/demo/` with `@RequestMapping("/demo/form")` serves
> `/demo/form/…`, not `/demo/demo/form/…`. (Spring derives no prefix from packages,
> unlike Struts `@Namespace` / JFinal `AutoBindRoutes`.)

#### @RequestMapping options

```java
@RequestMapping(
    value = "/items",           // Path
    method = RequestMethod.GET, // HTTP method
    params = "version=2",       // Parameter condition
    headers = "X-Custom=foo",   // Header condition
    consumes = "application/json",  // Content-Type
    produces = "application/json"   // Accept
)
public List<Item> getItems() { ... }
```

#### Multiple path mapping

```java
@GetMapping(value = {"/items", "/items/all"})
public List<Item> getAllItems() { ... }

@PatchMapping(value = "/{id}", path = "/{id}/patch")
public Item patchItem(@PathVariable Long id) { ... }
```

### 3.2 @RestController vs @Controller

| Feature | @RestController | @Controller |
|---------|-----------------|-------------|
| Response handling | Auto-serialize to JSON/XML | View resolver |
| Typical use | REST API | HTML pages |
| @ResponseBody | Auto-included | Must add explicitly |

```java
// REST API controller
@RestController
@RequestMapping("/api")
public class ApiController {
    @GetMapping("/data")
    public DataItem getData() {
        return new DataItem("value");  // Auto-serialized to JSON
    }
}

// Traditional controller
@Controller
public class ViewController {
    @GetMapping("/page")
    @ResponseBody  // Required for JSON response
    public DataItem getPage() {
        return new DataItem("value");
    }
}
```

### 3.3 Parameter binding annotations

#### @PathVariable - path parameters

```java
@GetMapping("/{id}")
public User getUser(@PathVariable Long id) { ... }

// With regex constraint
@GetMapping("/{id:\\d+}")
public User getUserById(@PathVariable Long id) { ... }

// Multiple path parameters
@GetMapping("/users/{userId}/posts/{postId}")
public Post getUserPost(
    @PathVariable Long userId,
    @PathVariable Long postId
) { ... }

// Optional path variable
@GetMapping("/{id:.+}")
public User getUser(@PathVariable(required = false) String id) { ... }
```

#### @RequestParam - query parameters

```java
@GetMapping("/search")
public List<User> searchUsers(
    @RequestParam String name,                          // Required
    @RequestParam(defaultValue = "10") int limit,       // With default
    @RequestParam(required = false) String sort         // Optional
) { ... }

// Bind all to Map
@GetMapping("/filter")
public List<User> filter(@RequestParam Map<String, String> params) { ... }
```

#### @RequestBody - request body

```java
@PostMapping("/users")
public User createUser(@RequestBody User user) { ... }

@PatchMapping("/{id}")
public User partialUpdate(
    @PathVariable Long id,
    @RequestBody Map<String, Object> updates
) { ... }

// With validation
@PostMapping("/users")
public User createUser(@Valid @RequestBody User user) { ... }
```

#### Other parameter annotations

| Annotation | Source | Example |
|------------|--------|---------|
| `@RequestHeader` | HTTP header | `@RequestHeader("Authorization") String token` |
| `@CookieValue` | Cookie | `@CookieValue("JSESSIONID") String sessionId` |
| `@ModelAttribute` | Form data | `@ModelAttribute User user` |

### 3.4 Spring Data REST auto-generated endpoints

A `@RepositoryRestResource` repository exposes CRUD endpoints with no controller class:

```java
@RepositoryRestResource(path = "users", itemResourceRel = "user")
public interface UserRepository extends CrudRepository<User, Long> { }
```

**Auto-generated endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users` | List all users |
| GET | `/users/{id}` | Get single user |
| POST | `/users` | Create user |
| PUT | `/users/{id}` | Update user |
| DELETE | `/users/{id}` | Delete user |

Custom finder methods annotated `@RestResource` add search endpoints:

```java
public interface UserRepository extends CrudRepository<User, Long> {

    @RestResource(path = "by-email", rel = "by-email")
    List<User> findByEmail(@Param("email") String email);

    @RestResource(path = "by-status", rel = "by-status")
    List<User> findByStatus(@Param("status") Status status);
}
```

**Auto-generated query endpoints:**
- `GET /users/search/by-email?email=value`
- `GET /users/search/by-status?status=value`

### 3.5 Transitive closure — meta-annotations and abstract base classes

A literal grep for `@RestController` / `@Controller` finds direct uses but misses two
indirection patterns common in real projects. **This is the #1 worker slip-up** — the
controller set must be the full transitive closure, not the direct hits.

#### Meta-annotations

Some projects define a custom annotation that itself carries `@RestController` (and
often a class-level `@RequestMapping`), so callers don't repeat the boilerplate:

```java
@RestController
@RequestMapping("/api/v1")
@Target(ElementType.TYPE)
@Retention(RetentionPolicy.RUNTIME)
public @interface ApiV1Controller { }

// Usage — no @RestController in sight on the controller itself:
@ApiV1Controller
public class UserController {
    @GetMapping("/users") public List<User> list() { ... }
    // → /api/v1/users
}
```

To find these: search for `@interface` declarations that themselves carry
`@RestController` or `@Controller`, then treat each as another controller-marker
annotation and grep for its uses.

#### Abstract base class

Routing annotations placed on an abstract base class are inherited by subclasses:

```java
@RestController
@RequestMapping("/api")
public abstract class BaseApiController { ... }

public class UserController extends BaseApiController {
    @GetMapping("/users") public List<User> list() { ... }
    // → /api/users (prefix inherited from base)
}
```

To find these: when you find a class annotated `@RestController` / `@Controller`
that is `abstract`, also grep for its subclasses (`extends <BaseName>`). When
composing endpoints, walk up the inheritance chain to collect class-level
`@RequestMapping` prefixes.

#### Building the controller set

Combine the two patterns above with the direct case into a transitive closure:

1. Find direct `@RestController` / `@Controller` uses.
2. Find meta-annotations that carry these annotations; recurse on their uses.
3. Find abstract `@RestController` / `@Controller` classes; find their subclasses.
4. Repeat until no new classes appear.

In most projects the closure is shallow, but the layer is exactly where small models
slip up.

### 3.6 Locating controller methods

#### AST search patterns

```java
// Search for controller annotations
ast_grep_search(pattern='@RestController', lang='java')
ast_grep_search(pattern='@Controller', lang='java')

// Search for mapping annotations
ast_grep_search(pattern='@GetMapping($PATH)', lang='java')
ast_grep_search(pattern='@PostMapping($PATH)', lang='java')
ast_grep_search(pattern='@PutMapping($PATH)', lang='java')
ast_grep_search(pattern='@DeleteMapping($PATH)', lang='java')
ast_grep_search(pattern='@PatchMapping($PATH)', lang='java')
ast_grep_search(pattern='@RequestMapping($$$)', lang='java')
```

#### Regex search patterns

```regex
@(GetMapping|PostMapping|PutMapping|DeleteMapping|PatchMapping|RequestMapping)\s*\(
```

#### Key directories to check

For multi-module projects, see [Project Structure](project-structure.md) —
controllers may reside in any module, not just the one with `@SpringBootApplication`.
Common controller package names: `controller`, `controllers`, `api`, `resource`,
`rest`. In a multi-module project each module has its own `src/main/java/` tree, so
grep across all of them rather than relying on directory convention:

```bash
grep -rl '@RestController\|@Controller' --include='*.java' .
```

*Illustration (a multi-module app):* controllers are spread across modules —
`app-admin/.../controller/` (admin, where `Application.java` lives),
`app-quartz/.../controller/` (scheduled-task controllers), and
`app-generator/.../controller/` (code-generator controller). The entry-point
module is *not* the only one with controllers.

#### Actuator mappings endpoint

If Spring Boot Actuator is enabled, the live mapping table is the ground truth:

```bash
curl http://localhost:8080/actuator/mappings
```

Response shows all registered mappings:
```json
{
  "dispatcherServlets": {
    "dispatcherServlet": [
      {
        "handler": "com.example.controller.UserController#getUser(Long)",
        "predicate": "{GET /api/users/{id}}"
      }
    ]
  }
}
```
