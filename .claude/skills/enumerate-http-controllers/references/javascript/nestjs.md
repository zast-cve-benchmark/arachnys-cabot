# NestJS Endpoint Enumeration Reference

NestJS is a **per-class-prefix annotation** framework: each `@Controller("x")` class
is a registration root carrying its own class-level prefix (the `@Controller`
argument); the method decorator (`@Get`/`@Post`/…) appends to it. The main agent
finds the roots and hands the worker only the deployment (L1) prefix — the global
prefix from `app.setGlobalPrefix(...)`; the worker composes each class's own
`@Controller` prefix itself. This file is split so the main agent reads §1–§2 and the
worker reads §1 + §3.

---

## 1. Identify

One grep-able signal per layer confirms NestJS:

- **Dependency marker** (`package.json`): `@nestjs/core` / `@nestjs/common`.
- **Class / module marker**: `@Controller("x")` on a class, `@Module({controllers:[...]})`.
- **Mapping marker**: `@Get(...)` / `@Post(...)` (and the other HTTP-verb variants)
  on methods.
- **Global-prefix marker**: `app.setGlobalPrefix(...)` in the bootstrap (`main.ts`).

---

## 2. Structural traversal — main agent

Walk the layer checklist for NestJS, descend to the registration-root layer, and
dispatch a worker below it. (Worker: skip to §3.)

### L1 Deployment

The deployment prefix is the global prefix from `app.setGlobalPrefix("/api")` in the
bootstrap (typically `main.ts`), if any, plus any versioning configured there
(`app.enableVersioning(...)`). Absent → the app mounts at `/`.

### L3 Registration root

Each `@Controller("x")` class is a registration root; its `@Controller` argument is
that root's class-level prefix. Find the roots by grepping `@Controller` across the
modules:

```bash
grep -rl '@Controller' --include='*.ts' .
```

Modules wire controllers in via `@Module({ controllers: [...] })`, so a controller
file lives wherever its module does. The package / directory is **never** a URL
segment — only the `@Controller` argument is.

### Prefix composition

```
endpoint = global prefix (L1) + class @Controller prefix (L3) + method path (L4)
```

Because one worker scope holds several controller classes that do not share a class
prefix, the main agent hands only the **L1** segment (the global prefix); each
class's `@Controller` prefix is the worker's to compose.

### Dispatch contract
- One worklist entry = one controller **directory / module** (group controllers, NOT
  one entry per `@Controller` class) — grouping classes under one worker avoids
  worker explosion on large apps.
- Hand each worker: `framework=nestjs`, `prefix=<the global prefix, or "">` (L1 ONLY
  — the per-class `@Controller` prefix is the worker's to compose),
  `location=<the controllers dir, or a representative controller file>`,
  `scope=<the controller files glob>`.
- Split / merge: one entry per module / dir. Do NOT split a module into per-class
  entries; do NOT merge across different global prefixes / versions.

---

## 3. Handler enumeration — worker

Given one controller directory's scope, enumerate every routed method. (Main agent:
you already did §2; skip to your next root.) At endpoint-composition time apply the
main agent's **L1** global prefix + **this class's own** `@Controller` prefix + the
method path — the package directory is never a prefix.

### 3.1 Route decorators

#### Controller and HTTP method decorators

| Decorator | Description |
|-----------|-------------|
| `@Controller(path?)` | Define controller with optional base path |
| `@Get(path?)` | Map GET request |
| `@Post(path?)` | Map POST request |
| `@Put(path?)` | Map PUT request |
| `@Delete(path?)` | Map DELETE request |
| `@Patch(path?)` | Map PATCH request |
| `@Head(path?)` | Map HEAD request |
| `@Options(path?)` | Map OPTIONS request |
| `@All(path?)` | Handle all HTTP methods |

The HTTP method comes from the decorator name; the endpoint path is the
global prefix + the class's `@Controller` prefix + the method-decorator path.

#### Basic controller pattern

```typescript
import { Controller, Get, Post, Put, Delete, Body, Param } from '@nestjs/common';

@Controller('cats')
export class CatsController {

  @Get()
  findAll(): string {
    return 'This action returns all cats';
  }

  @Get(':id')
  findOne(@Param('id') id: string): string {
    return `This action returns cat #${id}`;
  }

  @Post()
  create(@Body() createCatDto: CreateCatDto): string {
    return 'This action adds a new cat';
  }

  @Put(':id')
  update(@Param('id') id: string, @Body() updateCatDto: UpdateCatDto): string {
    return `This action updates cat #${id}`;
  }

  @Delete(':id')
  remove(@Param('id') id: string): string {
    return `This action removes cat #${id}`;
  }
}
```

### 3.2 Parameter decorators

#### Request parameter decorators

| Decorator | Source | Example |
|-----------|--------|---------|
| `@Param(key?)` | Route params | `@Param('id') id: string` |
| `@Query(key?)` | Query string | `@Query('limit') limit: number` |
| `@Body(key?)` | Request body | `@Body() dto: CreateUserDto` |
| `@Headers(key?)` | HTTP headers | `@Headers('auth') auth: string` |
| `@Req()` | Full Request | `@Req() request: Request` |
| `@Res()` | Full Response | `@Res() response: Response` |
| `@Session()` | Session data | `@Session() session: any` |
| `@Ip()` | Client IP | `@Ip() ip: string` |
| `@HostParam(key?)` | Hostname param | `@HostParam('account') account: string` |

#### Parameter examples

```typescript
@Get(':id')
findOne(
  @Param('id') id: string,           // Route parameter
  @Query('include') include: string, // Query parameter
  @Headers('x-token') token: string, // Header
  @Req() request: Request            // Full request
): string {
  return `Cat #${id}`;
}
```

### 3.3 Response decorators

| Decorator | Description |
|-----------|-------------|
| `@HttpCode(code)` | Set HTTP status code |
| `@Header(name, value)` | Set response header |
| `@Redirect(url, statusCode?)` | Redirect response |
| `@Render(view)` | Render template |

```typescript
@Post()
@HttpCode(201)
@Header('X-Custom-Header', 'value')
create(@Body() dto: CreateUserDto) {
  return { message: 'User created' };
}

@Get('docs')
@Redirect('https://docs.nestjs.com', 302)
getDocs() {}
```

### 3.4 Dynamic routes

#### Path parameters

```typescript
@Controller('users')
export class UsersController {

  // Single parameter
  @Get(':id')
  findOne(@Param('id') id: string) {
    return `User #${id}`;
  }

  // Multiple parameters
  @Get(':userId/posts/:postId')
  getUserPost(
    @Param('userId') userId: string,
    @Param('postId') postId: string
  ) {
    return `User ${userId}, Post ${postId}`;
  }
}
```

Route params use the `:id` syntax in the decorator path; they bind to the method
via `@Param`.

#### Wildcard routes

```typescript
@Get('files/*')
getFiles(@Param('0') path: string) {
  return `File path: ${path}`;
}
```

#### Sub-domain routing

```typescript
// admin.example.com/*
@Controller({ host: 'admin.example.com' })
export class AdminController {
  @Get()
  index() {
    return 'Admin page';
  }
}

// :account.example.com/*
@Controller({ host: ':account.example.com' })
export class AccountController {
  @Get()
  getInfo(@HostParam('account') account: string) {
    return account;
  }
}
```

### 3.5 Versioning

When `app.enableVersioning(...)` is configured in the bootstrap, `@Version` on a
controller or method adds a version segment to the route; it is part of the L1
deployment configuration handed down by the main agent.

### 3.6 Module organization

Controllers are wired into the app via `@Module({ controllers: [...] })`. The module
declaration tells you which controller classes are active, but contributes **no** URL
segment of its own.

```typescript
import { Module } from '@nestjs/common';
import { CatsController } from './cats.controller';
import { CatsService } from './cats.service';

@Module({
  controllers: [CatsController],
  providers: [CatsService],
})
export class CatsModule {}
```

A dynamic module registers controllers/providers at runtime via a static factory,
but the controller set is still declared in `controllers: [...]`:

```typescript
@Module({})
export class ConfigModule {
  static register(options: Record<string, any>): DynamicModule {
    return {
      module: ConfigModule,
      providers: [{ provide: 'CONFIG_OPTIONS', useValue: options }],
      exports: ['CONFIG_OPTIONS'],
    };
  }
}
```

### 3.7 Guards and interceptors

Guards (`@UseGuards`) and interceptors apply authentication / cross-cutting logic but
**do not change routing** — a guarded method is still the same endpoint. Treat
`@UseGuards` at controller or method level as security metadata, not a route segment.

```typescript
import { CanActivate, ExecutionContext, Injectable } from '@nestjs/common';

@Injectable()
export class AuthGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const request = context.switchToHttp().getRequest();
    return request.user?.isValid ?? false;
  }
}
```

```typescript
// Controller-level
@Controller('admin')
@UseGuards(AuthGuard)
export class AdminController { }

// Method-level
@Controller('users')
export class UsersController {
  @Get()
  @UseGuards(AuthGuard)
  findAll() { }
}
```

### 3.8 WebSocket gateways

A `@WebSocketGateway` is a WebSocket surface, not an HTTP route — `@SubscribeMessage`
handlers respond to socket messages, not HTTP requests:

```typescript
import {
  WebSocketGateway,
  WebSocketServer,
  SubscribeMessage,
  MessageBody,
} from '@nestjs/websockets';
import { Server } from 'socket.io';

@WebSocketGateway(80, { namespace: 'events' })
export class EventsGateway {
  @WebSocketServer() server: Server;

  @SubscribeMessage('events')
  handleEvent(@MessageBody() data: string) {
    return { event: 'events', data };
  }
}
```

### 3.9 Region anchoring

Anchor each handler's region at the handler **method body** — the routed method
annotated with `@Get`/`@Post`/etc.

### 3.10 Locating controller methods

#### AST search patterns

```typescript
// Search for controller classes
ast_grep_search(pattern='@Controller($PATH) class $NAME { $$$ }', lang='typescript')

// Search for HTTP method decorators
ast_grep_search(pattern='@Get($PATH) $$$', lang='typescript')
ast_grep_search(pattern='@Post($PATH) $$$', lang='typescript')
ast_grep_search(pattern='@Put($PATH) $$$', lang='typescript')
ast_grep_search(pattern='@Delete($PATH) $$$', lang='typescript')

// Search for parameter decorators
ast_grep_search(pattern='@Param($NAME) $TYPE $VAR', lang='typescript')
ast_grep_search(pattern='@Body() $VAR', lang='typescript')
```

#### Regex search patterns

```regex
@Controller\s*\(
@(Get|Post|Put|Delete|Patch)\s*\(
@Param\s*\(
@Body\s*\(
@Query\s*\(
class\s+\w+Controller
@WebSocketGateway
```

#### Key files to check

| Directory | Purpose |
|-----------|---------|
| `src/controllers/` | Controller definitions |
| `src/modules/` | Module definitions |
| `src/api/` | API endpoints |
| `src/gateways/` | WebSocket gateways |
