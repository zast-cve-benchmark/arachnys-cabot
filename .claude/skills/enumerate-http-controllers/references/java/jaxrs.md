# JAX-RS Endpoint Enumeration Reference

JAX-RS (Java API for RESTful Web Services) is a **per-class-prefix annotation**
framework: each resource class declares its own `@Path` prefix and each method its
own sub-path. What sets it apart from Spring is the **deployment layering** — context
path, framework mount (`cxf.path`), and, under Apache CXF, **one `setAddress(...)`
per server container** — all stack in front of the resource `@Path`. Getting those
deployment layers right (especially the CXF per-container address) is the whole game;
the per-method handler reading is routine.

---

## 1. Identify

Confirm JAX-RS is in use via one grep-able signal at each level:

- **Dependency markers (pom / build file):** `javax.ws.rs` or `jakarta.ws.rs`
  (the spec), plus an implementation — Jersey (`org.glassfish.jersey`), RESTEasy
  (`org.jboss.resteasy`), or **Apache CXF** (`org.apache.cxf`,
  `cxf-rt-frontend-jaxrs`).
- **Class marker:** a resource class annotated `@Path("...")`.
- **Method markers:** `@GET` / `@POST` / `@PUT` / `@DELETE` / `@PATCH` /
  `@HEAD` / `@OPTIONS` on resource methods.
- **CXF deployment markers:** a `cxf.path` property (in `application.properties` /
  `application.yml`), and a config class building a `JAXRSServerFactoryBean` /
  `SpringJAXRSServerFactoryBean` with `setAddress(...)`.

---

## 2. Structural traversal — main agent

The main agent owns the deployment prefix and the registration roots. It walks the
layers top-down, then dispatches one worker per resource-package-behind-a-container.
It does **not** read individual handler methods (that is §3).

### L1 Deployment — the stacked prefix

The full endpoint path composes **every** layer in front of the method:

```
contextPath + <app base> + resource @Path + method @Path
```

`contextPath` + `<app base>` are L1 deployment (main-agent territory, composed here);
the resource and method `@Path` are per-resource/per-method (worker territory, §3).

- **`contextPath`** — the servlet/app context path, from config.
- **`<app base>`** — the JAX-RS application's own mount. **It comes from one of three
  deployment styles — identify which the project uses; only ONE applies, and it is the
  most-dropped layer.** Whichever it is, the base is a real config value with a
  `file:line` — never assume a convention like `/api`:
  1. **Servlet-mapped Jersey/RESTEasy (most common, NON-CXF).** The JAX-RS runtime is
     a servlet (`org.glassfish.jersey.servlet.ServletContainer`, or RESTEasy's
     `HttpServletDispatcher`) whose `web.xml` `<servlet-mapping><url-pattern>` IS the
     app base — **strip the trailing `/*`**. `<url-pattern>/v1/*</url-pattern>` → base
     `/v1`. (RESTEasy may instead set `resteasy.servlet.mapping.prefix`.) Grep the
     module's `web.xml` for `<url-pattern>` next to a Jersey/RESTEasy `<servlet-class>`.
  2. **`@ApplicationPath("/x")`** on an `Application` / `ResourceConfig` subclass (see
     L3 below) → base `/x`. Used when the app is servlet-3.0 annotation-bootstrapped
     (no web.xml mapping). If BOTH a web.xml `<url-pattern>` and `@ApplicationPath`
     exist, the web.xml mapping wins (it overrides the annotation).
  3. **Apache CXF** — `cxf.path` + per-container `setAddress(...)` (detailed below).
- **`cxf.path`** — the global CXF mount, e.g. `/rest`, from config (CXF style only).
- **Each CXF container's `setAddress(...)`** — the per-container sub-mount. This is
  the layer that gets dropped. CXF apps can split JAX-RS resources across **several
  `JAXRSServerFactoryBean` containers**, each registered at its own sub-address, so a
  resource's full path includes *that container's* address on top of the global
  `cxf.path`. Per module, look in the CXF config class (a `*CXFContext.java` /
  `@Configuration` that builds a `JAXRSServerFactoryBean` /
  `SpringJAXRSServerFactoryBean`) for `setAddress(...)`:

  ```java
  container.setAddress("/foo");   // this container's resources mount under <cxf.path>/foo
  ```

  When you enumerate a module's services, grep that module for `setAddress(` (or
  `JAXRSServerFactoryBean`) to find every container sub-mount and prepend each
  container's address to its resources.

**This is the #1 miss for multi-module CXF apps.** A main API container mounts at the
bare `cxf.path`; additional containers — typically one per extension/secondary module
— each add their own `setAddress(...)` segment. **Dropping a container's `setAddress`
segment is both a miss AND a false positive** — you lose the real endpoint and emit a
wrong one at the un-prefixed path.

### L3 Registration root — what binds a prefix to a resource set

A **registration root** here is either a CXF container (its `setAddress` + the
resources it registers) or a JAX-RS `Application` / `ResourceConfig` registration.
Each `@Path` resource is the routing/region unit; in interface-driven projects the
**interface declares the routing (`@Path`) and the impl gives the region** — read
both. The two non-CXF registration mechanisms:

**`@ApplicationPath` Application class** — adds an application base path and lists the
resource classes:

```java
@ApplicationPath("/api")
public class MyApplication extends Application {
    @Override
    public Set<Class<?>> getClasses() {
        return Set.of(UserResource.class, OrderResource.class);
    }
}
```

**`ResourceConfig` registration (Jersey)** — same base path, resources registered by
package scan or individually:

```java
@ApplicationPath("/api")
public class MyApplication extends ResourceConfig {
    public MyApplication() {
        packages("com.example.resources");
        // Or register individually
        register(UserResource.class);
        register(OrderResource.class);
    }
}
```

### Prefix composition — worked examples

**Servlet-mapped Jersey/RESTEasy (most common).** A `web.xml` maps the Jersey
servlet at `<url-pattern>/v1/*</url-pattern>` (no contextPath override → app at root),
a resource `@Path("/users")`, a method `@Path("/{id}")`:

```
""  +  /v1  +  /users  +  /{id}   →   /v1/users/{id}
```

(Illustration only. The `/v1` came from the servlet `<url-pattern>` in web.xml — read
it, do not assume `/api`. Drop it and you emit `/users/{id}`: a miss AND a false
positive, since the un-prefixed path is not served.)

**CXF.** `contextPath=/app`, `cxf.path=/services`, a container at `setAddress("/foo")`,
a resource `@Path("users")`, a method with no sub-path:

```
/app  +  /services  +  /foo  +  users   →   /app/services/foo/users
```

(Drop the `/foo` container segment and you produce `/app/services/users` — both a
miss and a false positive.)

### Dispatch contract
- One worklist entry = one JAX-RS resource **package per CXF container** (the set of
  resources sharing one container's `setAddress`). One container with many resources
  → group by package; do not split per resource class.
- Hand each worker: `framework=jaxrs`,
  `prefix=<contextPath + cxf.path + this container's setAddress>` (the L1 deployment
  + container layers, ALREADY composed — but NOT the resource-class `@Path`, which
  is per-class and the worker composes),
  `location=<the CXF config class mounting this container, file:line, or a
  representative resource>`, `scope=<resource package glob>`.
- Split / merge: **one entry per CXF container** — each `setAddress` is a distinct
  prefix; never drop the container segment (it is both a miss and a false positive).
  Within a container, group resources by package.

---

## 3. Handler enumeration — worker

Given one root's scope (a resource package, with the main agent's composed L1 prefix
in hand), enumerate each routed method. **Compose the final endpoint** by applying the
main agent's L1 prefix (the deployment base — servlet `<url-pattern>`, `@ApplicationPath`,
or CXF `contextPath + cxf.path + setAddress`, already composed for you) **+ this
resource's `@Path` + this method's `@Path`**. Apply the handed prefix verbatim; do not
recompose or second-guess it. In interface-driven projects the routing
annotations may live on the interface while the implementation carries the body — this
is a transitive read: **read both the interface (for routing) and the impl (for
region)**.

### 3.1 @Path at class and method level

`@Path` applies at class and/or method level to define URL paths:

```java
@Path("/users")
public class UserResource {

    @GET
    public List<User> getAllUsers() { ... }

    @GET
    @Path("/{id}")
    public User getUser(@PathParam("id") Long id) { ... }
}
```

**HTTP method annotations:**

| Annotation | HTTP Method | Description |
|------------|-------------|-------------|
| `@GET` | GET | Retrieve resources |
| `@POST` | POST | Create resources |
| `@PUT` | PUT | Replace resources |
| `@DELETE` | DELETE | Delete resources |
| `@PATCH` | PATCH | Partial update |
| `@HEAD` | HEAD | Headers only |
| `@OPTIONS` | OPTIONS | CORS preflight |

```java
@Path("/items")
public class ItemResource {

    @GET
    public List<Item> list() { ... }

    @POST
    public Item create(Item item) { ... }

    @PUT
    @Path("/{id}")
    public Item update(@PathParam("id") Long id, Item item) { ... }

    @DELETE
    @Path("/{id}")
    public void delete(@PathParam("id") Long id) { ... }
}
```

### 3.2 Parameter binding annotations

These tell you where each input comes from — the attack-surface map for the handler.

**`@PathParam` — URL path parameters:**

```java
@GET
@Path("/{id}")
public User getUser(@PathParam("id") Long id) { ... }

// Multiple path parameters
@GET
@Path("/{userId}/posts/{postId}")
public Post getPost(
    @PathParam("userId") Long userId,
    @PathParam("postId") Long postId
) { ... }

// With regex constraint
@Path("{id: \\d+}")
public User getUser(@PathParam("id") Long id) { ... }
```

**`@QueryParam` — query parameters:**

```java
@GET
public List<User> searchUsers(
    @QueryParam("name") String name,
    @QueryParam("page") @DefaultValue("1") int page,
    @QueryParam("size") @DefaultValue("10") int size
) { ... }
```

**`@FormParam` — form data:**

```java
@POST
@Consumes(MediaType.APPLICATION_FORM_URLENCODED)
public User createUser(
    @FormParam("name") String name,
    @FormParam("email") String email
) { ... }
```

**`@HeaderParam` — HTTP headers:**

```java
@GET
public User getCurrentUser(@HeaderParam("Authorization") String auth) { ... }
```

**`@CookieParam` — cookies:**

```java
@GET
public User getUser(@CookieParam("sessionId") String sessionId) { ... }
```

**`@MatrixParam` — matrix parameters:**

```java
@GET
@Path("/search")
public List<Item> search(@MatrixParam("color") String color) { ... }
// URL: /search;color=red
```

### 3.3 @Consumes / @Produces and the entity body

```java
@Path("/users")
@Consumes(MediaType.APPLICATION_JSON)
@Produces(MediaType.APPLICATION_JSON)
public class UserResource {

    @POST
    public User create(User user) { ... }

    @GET
    @Produces({MediaType.APPLICATION_JSON, MediaType.APPLICATION_XML})
    public List<User> list() { ... }
}
```

**Entity parameter (request body)** — an unannotated method parameter is deserialized
from the request body:

```java
@POST
public Response createUser(User user) {
    // User is automatically deserialized from request body
    return Response.created(uri).entity(user).build();
}

@PUT
@Path("/{id}")
public User updateUser(@PathParam("id") Long id, User user) {
    // Both path param and entity
}
```

**Context injection** — `@Context`-injected parameters (`UriInfo`, `HttpHeaders`,
`HttpServletRequest`) are not user request parameters; note them but don't treat them
as request inputs:

```java
@GET
public Response getInfo(
    @Context UriInfo uriInfo,
    @Context HttpHeaders headers,
    @Context HttpServletRequest request
) { ... }
```

### 3.4 Sub-resource patterns (easily missed)

A resource can delegate part of its path tree to another class. The worker misses
these because the routed methods live in a *different* class than the one carrying the
top-level `@Path` — follow the delegation.

**Sub-resource locator** — a `@Path`-only method (no HTTP-method annotation) that
returns another resource object; that returned object's methods serve the sub-tree:

```java
@Path("/users")
public class UserResource {

    @Path("/{userId}/orders")
    public OrderResource getOrderResource() {
        return new OrderResource();
    }
}

public class OrderResource {
    @GET
    public List<Order> getOrders(@PathParam("userId") Long userId) { ... }
    // → GET /users/{userId}/orders
}
```

**Sub-resource method** — an HTTP-method-annotated method that *also* carries a deeper
`@Path`, serving the sub-tree directly:

```java
@Path("/users")
public class UserResource {

    @GET
    @Path("/{userId}/orders")
    public List<Order> getUserOrders(@PathParam("userId") Long userId) { ... }
    // → GET /users/{userId}/orders
}
```

### 3.5 Locating resource classes — search patterns

**AST search:**

```java
// Search for @Path annotation
ast_grep_search(pattern='@Path($PATH)', lang='java')

// Search for HTTP method annotations
ast_grep_search(pattern='@GET', lang='java')
ast_grep_search(pattern='@POST', lang='java')
ast_grep_search(pattern='@PUT', lang='java')
ast_grep_search(pattern='@DELETE', lang='java')

// Search for resource classes
ast_grep_search(pattern='@Path($PATH) class $NAME { $$$ }', lang='java')

// Search for parameter annotations
ast_grep_search(pattern='@PathParam($NAME) $TYPE $VAR', lang='java')
ast_grep_search(pattern='@QueryParam($NAME) $TYPE $VAR', lang='java')
```

**Regex search:**

```regex
@Path\s*\(
@(GET|POST|PUT|DELETE|PATCH)\s*
@PathParam\s*\(
@QueryParam\s*\(
@FormParam\s*\(
class\s+\w+\s*\{[^}]*@Path
extends\s+(Application|ResourceConfig)
```

**Key files to check:**

| Directory | Purpose |
|-----------|---------|
| `src/main/java/**/resources/` | JAX-RS resources |
| `src/main/java/**/api/` | API endpoints |
| `src/main/java/**/rest/` | REST controllers |
| `*Application.java` | Application config |
