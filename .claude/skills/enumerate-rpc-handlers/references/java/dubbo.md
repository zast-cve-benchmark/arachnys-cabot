# Apache Dubbo Handler Enumeration Reference (Java)

## Overview

Apache Dubbo is a Java RPC framework where the service contract is a plain Java interface. There
is no separate IDL format like `.thrift` or `.proto` — the interface itself is the IDL. The
application provides a class implementing that interface, annotated `@DubboService` (or the older
`@com.alibaba.dubbo.config.annotation.Service`), which is the handler. Each method declared in
the service interface is one RPC source.

---

## 1. IDL → handler method mapping

No name translation occurs. The interface method name is the RPC method name, used verbatim.

```java
// UserService.java — the service interface (this IS the IDL)
public interface UserService {

    UserDTO getUserById(Long userId);

    UserDTO updateProfile(Long userId, ProfileUpdateRequest request);

    void deleteUser(Long userId);
}
```

The handler class implements this interface:

```java
// UserServiceImpl.java — the handler (annotated with @DubboService)
@DubboService
public class UserServiceImpl implements UserService {

    @Override
    public UserDTO getUserById(Long userId) {
        return userRepository.findById(userId)
            .orElseThrow(() -> new ServiceException("User not found: " + userId));
    }

    @Override
    public UserDTO updateProfile(Long userId, ProfileUpdateRequest request) {
        User user = userRepository.findById(userId)
            .orElseThrow(() -> new ServiceException("User not found: " + userId));
        // apply updates
        user.setName(request.getName());
        user.setEmail(request.getEmail());
        return userRepository.save(user).toDTO();
    }

    @Override
    public void deleteUser(Long userId) {
        userRepository.deleteById(userId);
    }
}
```

`service` = `UserService` (the interface name), `method` = each interface method name
(`getUserById`, `updateProfile`, `deleteUser`), `region` = each handler method body in
`UserServiceImpl.java`.

---

## 2. Identifying handler classes — the @DubboService annotation

The annotation is the registration root. Find all handler classes:

```bash
# Apache Dubbo 3.x
grep -rl '@DubboService' --include='*.java' .

# Apache Dubbo 2.x (legacy)
grep -rl '@org.apache.dubbo.config.annotation.Service' --include='*.java' .

# Alibaba Dubbo (older, pre-Apache)
grep -rl '@com.alibaba.dubbo.config.annotation.Service' --include='*.java' .

# XML configuration (older style)
grep -rn '<dubbo:service interface=' --include='*.xml' .
```

Each `@DubboService`-annotated class is a handler. One handler class = one worklist entry.

The annotation may carry configuration attributes, none of which affect the method list:

```java
@DubboService(version = "1.0.0", group = "primary", timeout = 3000)
public class OrderServiceImpl implements OrderService { ... }
```

---

## 3. From handler class → service interface (the IDL)

Once you have the handler class, find the interface it implements — that interface is `idl_location`:

```java
public class UserServiceImpl implements UserService { ... }
//                                          ^-- this is the IDL
```

```bash
# If you know the handler class, find its interface declaration
grep -n 'implements' path/to/UserServiceImpl.java
```

The interface may be in a separate module or a shared API jar. In a typical Dubbo project layout,
the interface lives in a `*-api` or `*-interface` Maven module, while the implementation lives in
a `*-service` or `*-provider` module.

---

## 4. Method list source — always the interface, not the impl class

Read the interface to enumerate methods. The impl class may override inherited methods or contain
private helpers; the interface is the authoritative list of what Dubbo exposes as RPC.

```bash
# List all method signatures declared in the interface
grep -n '^\s\+\(public\s\+\)\?\(void\|[A-Z][a-zA-Z0-9<>]*\)\s\+\w\+(' \
  path/to/UserService.java
```

If the interface extends another interface, include the parent interface's methods — they are also
exposed as RPC:

```java
public interface ExtendedUserService extends UserService {
    List<UserDTO> listByRole(String role);  // additional method
    // + all methods inherited from UserService
}
```

```bash
# Find and open any extended interface
grep -n 'extends\|interface' path/to/ExtendedUserService.java
```

---

## 5. `region` — the handler method body

For every interface method, the `region` points at the method body in the handler impl class:

- `region.file_path`: relative path to the `@DubboService`-annotated impl class
- `region.start_line`: the `@Override public UserDTO getUserById(...)` signature line
- `region.end_line`: the closing `}` of that method

**Do NOT record the interface file as the region.** The interface contains only method signatures,
not logic. The auditor needs the impl body to trace data flow to sinks.

**Delegation to a base class:** if the handler impl delegates to a base class (e.g. the impl
overrides a method but calls `super.getUserById(...)` in the body), record the handler method body
(the override). The call-graph completion step follows the `super` delegation. Do not record the
base class method instead.

---

## 6. XML-configured services (older Dubbo style)

Pre-annotation Dubbo projects configure services via Spring XML:

```xml
<!-- dubbo-provider.xml -->
<dubbo:service interface="com.example.UserService"
               ref="userServiceImpl"
               version="1.0.0" />

<bean id="userServiceImpl" class="com.example.impl.UserServiceImpl" />
```

Find these:

```bash
grep -rn '<dubbo:service interface=' --include='*.xml' .
```

The `interface` attribute names the interface (= IDL); the `ref` attribute names the Spring bean
(= handler impl). The worklist entry is the same shape as the annotation case.

---

## 7. Multi-service projects

A Dubbo provider module typically exposes several services. Each `@DubboService` class is a
separate worklist entry and a separate worker dispatch.

```bash
# Count how many handler classes exist in the project
grep -rl '@DubboService' --include='*.java' . | wc -l
```

Do not merge two handler classes into one worker — each service interface is its own method
contract and its own `service` value in the output.

---

## 8. Enumeration checklist

- Find handler classes via `@DubboService` grep (and XML `<dubbo:service>` if present).
- For each handler class, find the interface it implements — the interface is the IDL.
- Read the interface (including any parent interfaces via `extends`) to enumerate methods.
- For each interface method, locate the `@Override` body in the impl class.
- Record `service` = interface name, `method` = interface method name, `region` = impl method body.
- Do NOT record the interface file as the region.
- Do NOT skip methods inherited from a parent interface — they are RPC sources.
- Do NOT skip utility methods on the service interface (e.g. version/echo methods) — they are real RPC methods and attack surface.
