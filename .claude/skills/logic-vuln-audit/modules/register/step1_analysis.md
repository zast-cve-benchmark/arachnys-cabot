# Registration Business Logic Analysis Guide

Module-specific guidance for Step 1 of the Register Agent pipeline.
Use alongside `@agents/BUSINESS_ANALYZER.md` (the generic framework).

---

## Scope

Analyze the **user registration** function: all code paths that allow new accounts
to be created, from HTTP entry point through database INSERT and post-registration
actions (welcome emails, activation links, auto-login, etc.).

---

## 1. Entry Point Discovery

Search for registration routes using language-specific patterns:

| Language | Route Patterns | Handler Patterns |
|----------|---------------|-----------------|
| Java | `@PostMapping("/register")`, `@RequestMapping("/signup")`, XML `<url-pattern>` | `register()`, `signup()`, `createUser()`, `doRegister()` |
| PHP | `Route::post('/register')`, `$router->post('/signup')` | `register()`, `store()`, `create()`, `signUp()` |
| Python | `path('register/')`, `@app.route('/signup')`, `@router.post('/register')` | `register_view()`, `signup()`, `RegisterView`, `CreateUserView` |
| Go | `r.POST("/register")`, `e.POST("/signup")` | `Register()`, `SignUp()`, `CreateUser()`, `HandleRegister()` |
| Node.js | `router.post('/register')`, `app.post('/signup')` | `register`, `signup`, `createUser`, `registerHandler` |

Also check for:
- Third-party OAuth/social registration callbacks (`/auth/callback`, `/oauth/register`)
- API versioned routes (`/api/v1/register`, `/api/v2/users`)
- GraphQL mutations (`createUser`, `register`)

Record: route path, HTTP method, controller class/file, handler function name.

---

## 2. Validation Point Checklist

Map every validation applied during registration:

### Identity Uniqueness
- Username uniqueness check (DB query vs. cache vs. none)
- Email uniqueness check
- Phone number uniqueness check
- Timing: when in the flow (before or after other validations)

### Input Format
- Username format (regex, length, allowed characters)
- Email format validation (regex vs. library vs. none)
- Phone number format validation
- Password format rules (length, complexity)

### Security Controls
- CAPTCHA presence and type (image, reCAPTCHA, hCaptcha, slider)
- CAPTCHA binding mechanism (session, token, cookie)
- Rate limiting (IP-based, session-based, global)
- CSRF token validation
- Invitation code / registration gate (if exists)

### Verification Flow
- Email verification (link, code, or none)
- SMS/phone verification (OTP, call, or none)
- Verification timing (before or after account creation)

---

## 3. Data Flow Analysis

Trace how registration data moves through the system:

### Input Processing
- Raw parameter reception (request body, form data, JSON)
- Type conversion and sanitization
- Default value injection (role, status, created_at)

### Sensitive Data Handling
- Password hashing algorithm (bcrypt, argon2, MD5, SHA, plaintext)
- Salt generation method (per-user, global, none)
- Password storage field and format

### Database Operations
- Which fields are INSERTed
- Which fields come directly from user input (mass assignment risk)
- Transaction boundaries around the INSERT
- Database-level constraints (UNIQUE index, NOT NULL, CHECK)

### Post-Registration
- Auto-login behavior (session creation, token issuance)
- Welcome email / activation email dispatch
- Default data initialization (profile, preferences, permissions)

---

## 4. Design Intent Recognition

Infer the developer's intended registration flow:

- Is registration open to all, or gated (invite-only, admin approval)?
- Is email/phone verification required before login?
- Are there anti-abuse measures (CAPTCHA, rate limiting)?
- Is there an account activation step separate from registration?
- What default role/permissions does a new account receive?

Document gaps between apparent intent and actual implementation.

---

## 5. Global Component Tracking

Identify all global components that intercept the registration request:

| Component Type | What to Look For |
|---------------|-----------------|
| Auth middleware | Does it skip auth for registration routes? Misconfigured skips? |
| CSRF middleware | Applied to registration POST? Token rotation? |
| Rate limiter | Covers registration endpoint? Limits per IP/session? |
| Input sanitizer | Global XSS/SQL filtering that affects registration fields |
| Logging | What registration data is logged? Passwords in logs? |
| Transaction manager | Auto-commit vs. explicit transaction on user creation |

---

## 6. Cross-Language Specifics

### Java (Spring)
- `@Validated` / `@Valid` on request DTOs
- `@Transactional` on service methods
- Spring Security `permitAll()` for register endpoint
- Password encoder bean configuration

### PHP (Laravel)
- Form Request validation classes
- Mass assignment `$fillable` / `$guarded` on User model
- `bcrypt()` / `Hash::make()` usage
- Middleware groups for `guest` routes

### Python (Django/Flask)
- `ModelForm` or `Serializer` field definitions
- `make_password()` / `set_password()` usage
- `@login_required` absence on register view
- Django signals (`post_save` on User)

### Go (Gin/Echo)
- Struct binding tags (`json`, `binding:"required"`)
- `ShouldBindJSON` / `Bind` for input parsing
- `bcrypt.GenerateFromPassword` usage
- GORM `Create()` with struct fields

### Node.js (Express/NestJS)
- Body parser / validation middleware (joi, express-validator, class-validator)
- Mongoose/Sequelize model hooks (`beforeCreate`)
- `bcrypt.hash()` usage
- Passport local strategy registration

---

## Output

Write `business_logic.json` following the schema in `@reference/JSON_SCHEMAS.md`.
Ensure `workflows[]` is non-empty and each workflow has complete `entry_point`,
`global_components`, `business_logic` steps, and `data_operations`.
