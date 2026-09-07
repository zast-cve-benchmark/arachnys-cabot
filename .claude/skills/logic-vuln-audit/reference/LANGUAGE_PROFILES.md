# Language & Framework Profiles

Detection profiles for identifying project technology stacks.
To add a new language, append a new section following the same structure.

---

## Java

```yaml
java:
  detection_files: ["pom.xml", "build.gradle", "build.gradle.kts"]
  source_extension: ".java"
  frameworks:
    web:
      - name: "Spring Boot"
        detection: ["spring-boot-starter-web", "org.springframework.boot"]
        route_patterns: ["@GetMapping", "@PostMapping", "@PutMapping", "@DeleteMapping", "@RequestMapping"]
        handler_pattern: "@Controller|@RestController"
      - name: "Spring MVC"
        detection: ["spring-webmvc", "org.springframework.web"]
        route_patterns: ["@RequestMapping"]
        handler_pattern: "@Controller"
      - name: "Struts2"
        detection: ["struts2-core", "org.apache.struts2"]
        route_patterns: ["struts.xml", "<action name="]
        handler_pattern: "extends ActionSupport"
      - name: "Play Framework"
        detection: ["com.typesafe.play"]
        route_patterns: ["conf/routes", "GET /", "POST /"]
        handler_pattern: "extends Controller"
    orm:
      - name: "MyBatis"
        detection: ["mybatis", "org.mybatis"]
        query_patterns: ["<select", "<insert", "<update", "<delete", "@Select", "@Insert"]
      - name: "Hibernate"
        detection: ["hibernate-core", "org.hibernate"]
        query_patterns: ["@Query", "createQuery", "HQL"]
      - name: "JPA"
        detection: ["javax.persistence", "jakarta.persistence", "spring-data-jpa"]
        query_patterns: ["@Query", "JpaRepository", "CrudRepository"]
      - name: "JDBC"
        detection: ["java.sql", "javax.sql"]
        query_patterns: ["PreparedStatement", "Statement.execute", "DriverManager.getConnection"]
    auth:
      - name: "Spring Security"
        detection: ["spring-boot-starter-security", "spring-security"]
        patterns: ["WebSecurityConfigurerAdapter", "SecurityFilterChain", "@PreAuthorize"]
      - name: "Shiro"
        detection: ["org.apache.shiro"]
        patterns: ["SecurityManager", "Subject.login", "@RequiresPermissions"]
      - name: "Sa-Token"
        detection: ["cn.dev33.satoken"]
        patterns: ["StpUtil.login", "StpUtil.checkLogin"]
      - name: "JWT"
        detection: ["io.jsonwebtoken", "com.auth0.jwt", "java-jwt"]
        patterns: ["Jwts.builder", "JWT.create", "JWT.decode"]

  entry_keywords:
    # login now covers ALL authentication-related functionality
    login: ["login", "signin", "doLogin", "authenticate", "/auth/login", "/api/login",
            "auth", "authorization", "bearer", "token", "jwt", "session", "cookie",
            "credential", "identity", "principal", "oauth", "oidc", "sso", "saml",
            "apikey", "api_key", "access_token", "refresh_token", "verify", "validate",
            "AuthController", "AuthService", "AuthFilter", "AuthMiddleware", "AuthConfig",
            "SecurityConfig", "TokenService", "SessionManager", "IdentityProvider"]
    register: ["register", "signup", "createUser", "createAccount", "/auth/register"]
    password_reset: ["forgot", "reset", "resetPassword", "forgotPassword", "/password/reset"]
    profile_update: ["updateProfile", "editProfile", "updateUser", "/user/update", "/profile"]
    payment: ["pay", "payment", "order", "checkout", "charge", "/api/pay", "/api/order"]
```

---

## PHP

```yaml
php:
  detection_files: ["composer.json", "composer.lock"]
  source_extension: ".php"
  frameworks:
    web:
      - name: "Laravel"
        detection: ["laravel/framework", "illuminate/"]
        route_patterns: ["Route::get", "Route::post", "Route::put", "Route::delete"]
        handler_pattern: "extends Controller"
      - name: "ThinkPHP"
        detection: ["topthink/framework", "topthink/think-"]
        route_patterns: ["Route::get", "Route::post", "->rule("]
        handler_pattern: "extends Controller"
      - name: "CodeIgniter"
        detection: ["codeigniter4/framework"]
        route_patterns: ["$routes->get", "$routes->post"]
        handler_pattern: "extends BaseController"
      - name: "Yii2"
        detection: ["yiisoft/yii2"]
        route_patterns: ["'urlManager'", "'rules'"]
        handler_pattern: "extends Controller"
      - name: "Symfony"
        detection: ["symfony/framework-bundle"]
        route_patterns: ["#[Route(", "@Route("]
        handler_pattern: "extends AbstractController"
    orm:
      - name: "Eloquent"
        detection: ["illuminate/database"]
        query_patterns: ["::where(", "::find(", "::create(", "DB::table"]
      - name: "ThinkORM"
        detection: ["topthink/think-orm"]
        query_patterns: ["Db::name(", "->where(", "->find()"]
      - name: "Doctrine"
        detection: ["doctrine/orm"]
        query_patterns: ["createQueryBuilder", "getRepository"]
    auth:
      - name: "Laravel Auth"
        detection: ["illuminate/auth"]
        patterns: ["Auth::attempt", "Auth::check", "auth()->user()"]
      - name: "JWT"
        detection: ["tymon/jwt-auth", "firebase/php-jwt"]
        patterns: ["JWTAuth::attempt", "JWT::encode", "JWT::decode"]

  entry_keywords:
    # login now covers ALL authentication-related functionality
    login: ["login", "doLogin", "signin", "/auth/login", "/login",
            "auth", "authorization", "bearer", "token", "jwt", "session", "cookie",
            "credential", "identity", "principal", "oauth", "oidc", "sso", "saml",
            "apikey", "api_key", "access_token", "refresh_token", "verify", "validate",
            "Auth::attempt", "Auth::check", "Auth::guard", "JWTAuth", "Passport",
            "AuthController", "AuthService", "AuthMiddleware", "SecurityMiddleware"]
    register: ["register", "signup", "doRegister", "/auth/register", "/register"]
    password_reset: ["forgot", "reset", "resetPassword", "/password/reset", "/forgot"]
    profile_update: ["profile", "updateProfile", "editUser", "/user/profile", "/profile/update"]
    payment: ["pay", "order", "checkout", "charge", "/payment", "/order"]
```

---

## Python

```yaml
python:
  detection_files: ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"]
  source_extension: ".py"
  frameworks:
    web:
      - name: "Django"
        detection: ["django", "Django"]
        route_patterns: ["path(", "url(", "re_path(", "urlpatterns"]
        handler_pattern: "class.*View|def.*request"
      - name: "Flask"
        detection: ["flask", "Flask"]
        route_patterns: ["@app.route", "@blueprint.route", "add_url_rule"]
        handler_pattern: "def.*():"
      - name: "FastAPI"
        detection: ["fastapi", "FastAPI"]
        route_patterns: ["@app.get", "@app.post", "@router.get", "@router.post"]
        handler_pattern: "async def|def"
      - name: "Tornado"
        detection: ["tornado"]
        route_patterns: ["(r\"", "URLSpec"]
        handler_pattern: "class.*RequestHandler"
    orm:
      - name: "Django ORM"
        detection: ["django.db"]
        query_patterns: [".objects.", ".filter(", ".exclude(", ".raw("]
      - name: "SQLAlchemy"
        detection: ["sqlalchemy", "SQLAlchemy"]
        query_patterns: ["session.query", "session.execute", "select("]
      - name: "Peewee"
        detection: ["peewee"]
        query_patterns: [".select(", ".where(", ".get()"]
    auth:
      - name: "Django Auth"
        detection: ["django.contrib.auth"]
        patterns: ["authenticate(", "login(", "@login_required", "LoginView"]
      - name: "Flask-Login"
        detection: ["flask-login", "flask_login"]
        patterns: ["login_user", "current_user", "@login_required"]
      - name: "JWT"
        detection: ["PyJWT", "djangorestframework-simplejwt", "flask-jwt-extended"]
        patterns: ["jwt.encode", "jwt.decode", "create_access_token"]

  entry_keywords:
    # login now covers ALL authentication-related functionality
    login: ["login", "signin", "authenticate", "/auth/login", "/api/login",
            "auth", "authorization", "bearer", "token", "jwt", "session", "cookie",
            "credential", "identity", "principal", "oauth", "oidc", "sso", "saml",
            "apikey", "api_key", "access_token", "refresh_token", "verify", "validate",
            "LoginView", "AuthView", "TokenAuth", "JWTAuthentication", "SessionAuth",
            "@login_required", "authenticate()", "is_authenticated", "get_user"]
    register: ["register", "signup", "create_user", "/auth/register", "/api/register"]
    password_reset: ["forgot", "reset", "password_reset", "/password/reset", "/forgot"]
    profile_update: ["profile", "update_profile", "edit_user", "/user/profile", "/profile"]
    payment: ["pay", "payment", "order", "checkout", "/api/pay", "/api/order"]
```

---

## Go

```yaml
golang:
  detection_files: ["go.mod", "go.sum"]
  source_extension: ".go"
  frameworks:
    web:
      - name: "Gin"
        detection: ["github.com/gin-gonic/gin"]
        route_patterns: [".GET(", ".POST(", ".PUT(", ".DELETE(", ".Handle("]
        handler_pattern: "func.*\\*gin.Context"
      - name: "Echo"
        detection: ["github.com/labstack/echo"]
        route_patterns: [".GET(", ".POST(", ".PUT(", ".DELETE("]
        handler_pattern: "func.*echo.Context"
      - name: "Fiber"
        detection: ["github.com/gofiber/fiber"]
        route_patterns: [".Get(", ".Post(", ".Put(", ".Delete("]
        handler_pattern: "func.*\\*fiber.Ctx"
      - name: "Beego"
        detection: ["github.com/beego/beego"]
        route_patterns: ["beego.Router", "beego.NSRouter"]
        handler_pattern: "type.*Controller struct"
      - name: "Chi"
        detection: ["github.com/go-chi/chi"]
        route_patterns: ["r.Get(", "r.Post(", "r.Put(", "r.Route("]
        handler_pattern: "func.*http.ResponseWriter.*\\*http.Request"
    orm:
      - name: "GORM"
        detection: ["gorm.io/gorm"]
        query_patterns: [".Where(", ".Find(", ".Create(", ".Raw(", ".Order("]
      - name: "sqlx"
        detection: ["github.com/jmoiron/sqlx"]
        query_patterns: ["sqlx.Get", "sqlx.Select", "db.Exec"]
      - name: "database/sql"
        detection: ["database/sql"]
        query_patterns: ["db.Query(", "db.Exec(", "db.QueryRow("]
    auth:
      - name: "JWT"
        detection: ["github.com/golang-jwt/jwt", "github.com/dgrijalva/jwt-go"]
        patterns: ["jwt.Parse", "jwt.NewWithClaims", "jwt.SigningMethod"]
      - name: "Casbin"
        detection: ["github.com/casbin/casbin"]
        patterns: ["casbin.NewEnforcer", "Enforce("]

  entry_keywords:
    # login now covers ALL authentication-related functionality
    login: ["login", "signin", "Login", "SignIn", "/auth/login", "/api/login",
            "auth", "Auth", "authorization", "Authorization", "bearer", "Bearer",
            "token", "Token", "jwt", "JWT", "session", "Session", "cookie", "Cookie",
            "credential", "Credential", "identity", "Identity", "principal", "Principal",
            "oauth", "OAuth", "oidc", "OIDC", "sso", "SSO", "saml", "SAML",
            "apikey", "ApiKey", "access_token", "AccessToken", "refresh_token",
            "verify", "Verify", "validate", "Validate", "Authenticate", "Authorize",
            "AuthHandler", "AuthMiddleware", "AuthConfig", "JWTConfig", "TokenConfig",
            "SecurityMiddleware", "VerifierPool", "ClaimsValidator", "getUserInfo"]
    register: ["register", "signup", "Register", "SignUp", "/auth/register"]
    password_reset: ["forgot", "reset", "ForgotPassword", "ResetPassword", "/password/reset"]
    profile_update: ["profile", "UpdateProfile", "EditUser", "/user/profile", "/profile"]
    payment: ["pay", "payment", "order", "Pay", "Order", "/api/pay", "/api/order"]
```

---

## Node.js

```yaml
nodejs:
  detection_files: ["package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml"]
  source_extension: [".js", ".ts", ".mjs"]
  frameworks:
    web:
      - name: "Express"
        detection: ["express"]
        route_patterns: ["app.get(", "app.post(", "app.put(", "router.get(", "router.post("]
        handler_pattern: "function.*req.*res|\\(req.*res\\).*=>"
      - name: "Koa"
        detection: ["koa"]
        route_patterns: ["router.get(", "router.post(", "router.put("]
        handler_pattern: "async.*ctx|ctx.*=>"
      - name: "NestJS"
        detection: ["@nestjs/core", "@nestjs/common"]
        route_patterns: ["@Get(", "@Post(", "@Put(", "@Delete("]
        handler_pattern: "@Controller"
      - name: "Fastify"
        detection: ["fastify"]
        route_patterns: ["fastify.get(", "fastify.post(", ".route({"]
        handler_pattern: "function.*request.*reply|async.*request.*reply"
      - name: "Hapi"
        detection: ["@hapi/hapi"]
        route_patterns: ["server.route({"]
        handler_pattern: "handler:"
    orm:
      - name: "Sequelize"
        detection: ["sequelize"]
        query_patterns: [".findAll(", ".findOne(", ".create(", ".query("]
      - name: "TypeORM"
        detection: ["typeorm"]
        query_patterns: ["getRepository", "createQueryBuilder", "@Entity"]
      - name: "Prisma"
        detection: ["@prisma/client"]
        query_patterns: ["prisma.", ".findMany(", ".findUnique(", ".create("]
      - name: "Mongoose"
        detection: ["mongoose"]
        query_patterns: [".find(", ".findById(", ".save(", "Schema("]
    auth:
      - name: "Passport"
        detection: ["passport"]
        patterns: ["passport.authenticate", "passport.use", "LocalStrategy"]
      - name: "JWT"
        detection: ["jsonwebtoken"]
        patterns: ["jwt.sign", "jwt.verify", "jwt.decode"]
      - name: "bcrypt"
        detection: ["bcrypt", "bcryptjs"]
        patterns: ["bcrypt.hash", "bcrypt.compare", "bcrypt.genSalt"]

  entry_keywords:
    # login now covers ALL authentication-related functionality
    login: ["login", "signin", "authenticate", "/auth/login", "/api/login",
            "auth", "authorization", "bearer", "token", "jwt", "session", "cookie",
            "credential", "identity", "principal", "oauth", "oidc", "sso", "saml",
            "apikey", "api_key", "access_token", "refresh_token", "verify", "validate",
            "passport.authenticate", "jwt.sign", "jwt.verify", "LocalStrategy",
            "AuthController", "AuthService", "AuthMiddleware", "TokenService"]
    register: ["register", "signup", "createUser", "/auth/register", "/api/register"]
    password_reset: ["forgot", "reset", "resetPassword", "/password/reset", "/forgot"]
    profile_update: ["profile", "updateProfile", "editUser", "/user/profile", "/profile"]
    payment: ["pay", "payment", "order", "checkout", "charge", "/api/pay", "/api/order"]
```

---

## Adding a New Language

To add support for a new language (e.g., Ruby, C#):

1. Create a new section in this file following the same structure
2. Define: `detection_files`, `source_extension`, `frameworks` (web/orm/auth), `entry_keywords`
3. No other files need modification — the Leader Agent reads this file dynamically
