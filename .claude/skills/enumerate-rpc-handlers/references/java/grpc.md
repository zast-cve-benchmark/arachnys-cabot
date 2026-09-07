# gRPC Handler Enumeration Reference (Java)

## Overview

gRPC services are declared in `.proto` files. The Java gRPC plugin generates a base class
`XGrpc.XImplBase` from each `service X { ... }` block. The application subclasses `XImplBase` and
overrides each method. Each `rpc` declaration in the proto `service` block is one RPC source.

---

## 1. IDL → handler method mapping — the PascalCase/camelCase split

**This is the most important naming rule in gRPC Java, and the most common source of errors.**

The proto IDL uses PascalCase for `rpc` names:

```proto
service UserService {
  rpc UpdateProfile (UpdateProfileRequest) returns (UpdateProfileResponse);
  rpc GetUser       (GetUserRequest)       returns (GetUserResponse);
}
```

The generated Java `XImplBase` uses camelCase for the method names:

```java
// Generated — do NOT record region here
public abstract static class UserServiceImplBase implements BindableService {
    public void updateProfile(UpdateProfileRequest request,
                              StreamObserver<UpdateProfileResponse> responseObserver) {
        asyncUnimplementedUnaryCall(...);
    }
    public void getUser(GetUserRequest request,
                        StreamObserver<GetUserResponse> responseObserver) {
        asyncUnimplementedUnaryCall(...);
    }
}
```

**In the output schema:**
- `method` = the **proto name** (PascalCase): `UpdateProfile`, `GetUser`
- `region` points at the **Java override** in the application impl class (camelCase: `updateProfile`, `getUser`)

The reason: downstream auditing tools and human reviewers look up methods by the proto name (the
canonical service contract). The region points at the code that actually runs. Never swap these.

---

## 2. Identifying the handler class

The handler class `extends XGrpc.XImplBase`. Find it:

```bash
# Find all gRPC handler impl classes
grep -rl 'extends.*ImplBase' --include='*.java' .

# Or for a specific service
grep -rn 'extends UserGrpc\.UserImplBase' --include='*.java' .
```

The result is the application's handler class (e.g. `UserServiceImpl`). Open it — this is
`handler_location`. The generated `XGrpc.java` file is NOT the handler; the `XImplBase` nested
class is generated scaffolding.

---

## 3. Method body signature

The Java override signature follows a fixed pattern:

```java
// UserServiceImpl.java — the handler class
public class UserServiceImpl extends UserGrpc.UserServiceImplBase {

  @Override
  public void updateProfile(UpdateProfileRequest request,
                             StreamObserver<UpdateProfileResponse> responseObserver) {
    // application logic here
    User updated = userRepo.update(request.getUserId(), request.getProfileData());
    responseObserver.onNext(UpdateProfileResponse.newBuilder()
        .setUser(updated).build());
    responseObserver.onCompleted();
  }

  @Override
  public void getUser(GetUserRequest request,
                      StreamObserver<GetUserResponse> responseObserver) {
    User user = userRepo.findById(request.getUserId());
    responseObserver.onNext(GetUserResponse.newBuilder().setUser(user).build());
    responseObserver.onCompleted();
  }
}
```

The `region` for `UpdateProfile` is the `updateProfile(...)` method body in `UserServiceImpl.java`
— the `@Override` line through the closing `}`.

---

## 4. Streaming RPCs — same handler rule

gRPC supports four call types; the handler method signature changes, but the `region` rule is the
same for all of them:

```proto
rpc ListUsers   (ListUsersRequest) returns (stream UserResponse);   // server-streaming
rpc UploadData  (stream DataChunk) returns (UploadResponse);        // client-streaming
rpc Chat        (stream ChatMsg)   returns (stream ChatMsg);        // bidi-streaming
```

```java
// Server-streaming: returns void, uses responseObserver
public void listUsers(ListUsersRequest req,
                      StreamObserver<UserResponse> responseObserver) { ... }

// Client-streaming: returns a StreamObserver
public StreamObserver<DataChunk> uploadData(
    StreamObserver<UploadResponse> responseObserver) { ... }

// Bidi-streaming: returns a StreamObserver
public StreamObserver<ChatMsg> chat(
    StreamObserver<ChatMsg> responseObserver) { ... }
```

Record the method body for each of these exactly as for unary RPCs — `method` is the proto name
(`ListUsers`, `UploadData`, `Chat`), `region` points at the Java override.

---

## 5. Service registration root

The handler is registered with the gRPC server at startup:

```java
// Standard programmatic registration
Server server = ServerBuilder.forPort(port)
    .addService(new UserServiceImpl())
    .addService(new OrderServiceImpl())
    .build()
    .start();
```

In Spring-based gRPC services (e.g. `grpc-spring-boot-starter`), the handler class bears a
`@GrpcService` annotation and is auto-detected:

```java
@GrpcService
public class UserServiceImpl extends UserGrpc.UserServiceImplBase { ... }
```

Find service registrations:

```bash
# Programmatic
grep -rn 'addService\|ServerBuilder\|\.forPort(' --include='*.java' .

# Spring annotation
grep -rl '@GrpcService' --include='*.java' .
```

One `.addService(...)` call per service class → one worklist entry per service.

---

## 6. Method list source — always the .proto, not the generated class

Read the `.proto` `service` block to enumerate methods. The generated `XGrpc.java` and `XImplBase`
are derived from the proto and contain the same methods, but:
- The generated file is often large and harder to parse.
- The proto is the canonical IDL — the `method` name in the output schema is the proto name.

```bash
# List all rpc declarations in a proto file
grep -E '^\s+rpc ' path/to/service.proto
```

If a project has multiple `.proto` files each declaring a `service`, each service is a separate
worklist entry.

---

## 7. `region` — the handler method span

- `region.file_path`: relative path to the application impl Java file (`UserServiceImpl.java`),
  NOT the generated `UserGrpc.java` or `UserGrpc.UserServiceImplBase`
- `region.start_line`: the `@Override public void updateProfile(...)` signature line (or the
  `public StreamObserver<...> uploadData(...)` line for client-streaming)
- `region.end_line`: the closing `}` of that method

---

## 8. Enumeration checklist

- Read the `.proto` `service` block — it is the authoritative method list.
- Find the handler class via `extends XGrpc.XImplBase` grep.
- For each proto `rpc`, find the camelCase Java override (`UpdateProfile` → `updateProfile`).
- Record `service` = proto service name, `method` = proto rpc name (PascalCase), `region` = Java override method body.
- Do NOT use the generated `XGrpc.java` file as the region.
- Do NOT use the camelCase Java name as `method` — use the PascalCase proto name.
- Do NOT skip streaming RPCs — they are full RPC sources and may carry unsanitized input.
- Do NOT skip protocol/utility RPC methods such as gRPC health-check methods (`grpc.health.v1.Health`) — they are real RPC methods and attack surface.
