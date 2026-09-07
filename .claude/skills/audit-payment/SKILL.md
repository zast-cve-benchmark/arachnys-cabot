---
name: audit-payment
description: Audit payment / order / billing endpoints. Produces business-logic-flaw (amount tampering, race conditions, refund abuse, coupon reuse, state-machine bypass, callback replay) and incorrect-authorization (cross-user payment ops) findings.
---

# Role

Specialist for `business-logic-flaw` / `incorrect-authorization` in payment flows.

# Trigger recap

Dispatched when identify-business-scenarios returns payment.

# SINK patterns

Key points from `logic-vuln-audit/modules/payment/` (payment_sinks_library.md has 46+ SINKs; the most critical categories are distilled below):

1. **Amount/quantity / price modifiable on client side**: `POST /api/order` accepts a `price` field instead of re-fetching SKU price from DB
2. **Negative / zero / extreme quantity**: missing validation -> price inversion / overflow / resource exhaustion
3. **Payment callback signature validation missing/bypassable**: third-party payment notification endpoint has no signature check or weak validation
4. **Callback replay**: callback for the same order processed multiple times -> duplicate shipment
5. **Order state machine bypass**: user can directly PATCH `status=paid` instead of going through the payment flow
6. **Refund logic**: refund unpaid orders; refund exceeding original amount; refund someone else's order
7. **Coupons/points**: reusable / stackable (when business rules forbid) / negative points
8. **Currency precision**: floating-point summation error; mixed cent/yuan units

Allowed `category_id` values for this skill: `business-logic-flaw`, `incorrect-authorization`.

# Safe context (false-positive prevention)

- Generic CRUD authorization bypass on non-payment resources → `audit-crud`, not here.
- SQL injection / SSRF in payment handlers → cross-cutting auditors handle the sink class, not here.
- Do not write PoCs in this skill.

# References (Read on demand)

Currently no framework-specific references; if/when needed, add `references/<framework>.md` and Read it conditionally.

# Output

1. `Skill(record-vulnerabilities)` to learn the output protocol
2. Write OUTPUT_FILE and run validate_vulns.py per record-vulnerabilities Steps 1-2.
