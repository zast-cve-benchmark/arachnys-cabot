# Cross-Function Exploit Chain Patterns

Known attack chain patterns that combine vulnerabilities from different business functions.
The Chain & Reporter Agent uses these patterns to identify exploitable chains.

---

## Chain Categories

### Category 1: Information Gathering → Account Takeover

These chains start with information leakage and escalate to full account compromise.

**CHAIN-PATTERN-01: User Enumeration → Password Brute Force**
```
login(info_leak) → login(brute_force)

Step 1: [LOGIN] Enumerate valid usernames via differential error messages
Step 2: [LOGIN] Brute force password for confirmed usernames
Prerequisite: Weak/missing rate limiting, no account lockout
Impact: Account takeover
Break at: Fix enumeration (Step 1) OR add rate limiting
```

**CHAIN-PATTERN-02: User Enumeration → Password Reset Token Prediction**
```
login(info_leak) + password_reset(token_prediction)

Step 1: [LOGIN/REGISTER] Enumerate valid user accounts
Step 2: [PASSWORD_RESET] Request reset for confirmed account
Step 3: [PASSWORD_RESET] Predict or brute-force the reset token
Step 4: [PASSWORD_RESET] Reset password to attacker-controlled value
Impact: Account takeover of any enumerated user
Break at: Fix enumeration OR use cryptographic random tokens
```

**CHAIN-PATTERN-03: Registration Info Leak → Profile IDOR**
```
register(enumeration) + profile_update(idor)

Step 1: [REGISTER] Enumerate existing users via registration endpoint
Step 2: [PROFILE_UPDATE] Access/modify profiles of enumerated users via IDOR
Impact: Mass data exposure or unauthorized profile modification
Break at: Fix enumeration OR fix IDOR
```

---

### Category 2: Authentication Bypass → Privilege Escalation

Chains that bypass authentication then escalate privileges.

**CHAIN-PATTERN-04: Login Bypass → Profile Privilege Escalation**
```
login(auth_bypass) + profile_update(mass_assignment)

Step 1: [LOGIN] Bypass authentication (weak JWT, default creds, etc.)
Step 2: [PROFILE_UPDATE] Escalate to admin via mass assignment (role/is_admin field)
Impact: Full admin access
Break at: Fix auth bypass OR fix mass assignment
```

**CHAIN-PATTERN-05: Registration Mass Assignment → Payment Abuse**
```
register(mass_assignment) + payment(amount_tampering)

Step 1: [REGISTER] Create account with elevated privileges via mass assignment
Step 2: [PAYMENT] Exploit privileged payment features (discount override, refund, etc.)
Impact: Financial loss
Break at: Fix registration mass assignment OR add payment authorization checks
```

**CHAIN-PATTERN-06: SSO/OAuth Flaw → Account Takeover → Data Exfil**
```
login(oauth_flaw) + profile_update(idor)

Step 1: [LOGIN] Exploit OAuth/SSO vulnerability (state bypass, redirect manipulation)
Step 2: [LOGIN] Gain access as victim user
Step 3: [PROFILE_UPDATE] Bind attacker's OAuth to victim account (persistence)
Impact: Persistent account takeover
Break at: Fix OAuth implementation
```

---

### Category 3: Multi-Function Financial Chains

Chains targeting payment/financial functions.

**CHAIN-PATTERN-07: Registration → Payment Fraud**
```
register(batch_registration) + payment(coupon_abuse)

Step 1: [REGISTER] Create multiple accounts via batch registration
Step 2: [PAYMENT] Claim new-user coupons/discounts on each account
Step 3: [PAYMENT] Stack or resell accumulated benefits
Impact: Financial loss, marketing budget abuse
Break at: Fix batch registration OR limit coupon per device/IP
```

**CHAIN-PATTERN-08: Profile Escalation → Payment Privilege Abuse**
```
profile_update(vertical_escalation) + payment(merchant_withdrawal)

Step 1: [PROFILE_UPDATE] Escalate to merchant/admin role
Step 2: [PAYMENT] Access merchant withdrawal or refund functions
Step 3: [PAYMENT] Withdraw funds or issue fraudulent refunds
Impact: Direct financial loss
Break at: Fix privilege escalation OR add payment authorization
```

**CHAIN-PATTERN-09: Password Reset → Payment Account Takeover**
```
password_reset(unauthorized_reset) + payment(wallet_drain)

Step 1: [PASSWORD_RESET] Reset victim's password without proper verification
Step 2: [LOGIN] Login as victim
Step 3: [PAYMENT] Transfer/withdraw victim's wallet balance
Impact: Account takeover + financial loss
Break at: Fix password reset authorization
```

---

### Category 4: Session/Token Manipulation Chains

Chains exploiting session management across functions.

**CHAIN-PATTERN-10: Session Fixation → Cross-Function Exploit**
```
register(session_fixation) + payment(order_hijack)

Step 1: [REGISTER] Exploit session fixation during registration
Step 2: [PAYMENT] Wait for victim to place order
Step 3: [PAYMENT] Access victim's order/payment via fixated session
Impact: Order hijacking, data exposure
Break at: Fix session regeneration
```

**CHAIN-PATTERN-11: JWT Weakness → Universal Access**
```
login(jwt_flaw) + profile_update + payment

Step 1: [LOGIN] Exploit JWT vulnerability (none algorithm, key confusion, no expiry)
Step 2: [PROFILE_UPDATE] Modify any user's profile
Step 3: [PAYMENT] Access any user's payment functions
Impact: Complete application compromise
Break at: Fix JWT implementation
```

---

### Category 5: Race Condition Chains

Chains exploiting timing/concurrency issues.

**CHAIN-PATTERN-12: Registration Race + Payment Race**
```
register(race_condition) + payment(double_spend)

Step 1: [REGISTER] Create duplicate accounts via race condition
Step 2: [PAYMENT] Exploit concurrent payment processing for double-spend
Impact: Multiple redemptions, financial loss
Break at: Add proper locking/transaction controls
```

---

## Chain Scoring Matrix

| Factor | 1 pt | 2 pts | 3 pts |
|--------|------|-------|-------|
| **Prerequisites** | Admin access needed | Normal user account | Unauthenticated |
| **Complexity** | Custom tooling/research | Standard tools (Burp, scripts) | Browser only |
| **Automation** | Manual only | Semi-automated | Fully scriptable |
| **Reliability** | < 50% success | 50-90% success | > 90% success |
| **Impact Scope** | Single user | Multi-user | Full system |
| **Detection** | Easy to detect/logged | Moderate detection | Hard to detect |
| **Persistence** | One-time | Session-level | Persistent |
| **Data Sensitivity** | Low sensitivity | Medium / business data | High / PII / Financial |

**Score → Severity**:
- 20-24 = Critical
- 15-19 = High
- 10-14 = Medium
- 8-9 = Low

---

## Chain Discovery Algorithm

```
FOR each pair (vuln_A, vuln_B) where vuln_A.module != vuln_B.module:
    1. Check if vuln_A's impact enables vuln_B's prerequisites
       e.g., vuln_A gives "valid user session" → vuln_B requires "authenticated"
    2. Check against known CHAIN-PATTERN templates above
    3. Check if combined impact > individual impacts
    4. IF viable: Score using the matrix, generate chain record

FOR each triple (vuln_A, vuln_B, vuln_C):
    Same checks but require sequential enablement: A enables B enables C

PRIORITY ORDER:
    1. Chains ending in financial impact (payment module)
    2. Chains ending in account takeover
    3. Chains ending in mass data exposure
    4. Chains ending in privilege escalation
```

---

## Chain PoC Requirements

Each confirmed chain needs a combined PoC that:

1. Executes each step sequentially
2. Passes output from step N as input to step N+1
3. Verifies success at each step before proceeding
4. Reports the combined impact
5. Identifies which fix breaks the chain (mitigation recommendation)
