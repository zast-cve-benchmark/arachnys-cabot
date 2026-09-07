# Payment Business Logic Analysis Guide

Analyze the project's payment-related business logic across all payment scenarios present in the codebase.

**CRITICAL**: Payment analysis has a two-phase Step 1 unlike other modules:
- **Phase 1a**: Scenario Identification -- determine which of 12 payment scenarios exist
- **Phase 1b**: Per-Scenario Business Analysis -- deep analysis of each identified scenario

---

## Phase 1a: Scenario Identification

Scan the codebase to determine which of these 12 payment scenarios are implemented.

### The 12 Payment Business Scenarios

| ID | Scenario | Key Indicators |
|----|----------|---------------|
| 1 | **E-Commerce** | Product purchase, shopping cart, order checkout |
| 2 | **Subscription/Membership** | Recurring billing, tier upgrade/downgrade, renewal |
| 3 | **Multi-Sided Platform** | Platform commission, merchant settlement, driver/rider split |
| 4 | **Prepayment/Reservation** | Deposits, final payments, deposit refunds |
| 5 | **Financial Payment** | Transfer, withdrawal, top-up, balance payment |
| 6 | **Content/Gaming** | Virtual currency recharge, item purchase, in-app purchase |
| 7 | **Enterprise B2B** | Corporate account payment, invoice management, batch settlement |
| 8 | **Crowdfunding/Donation** | Crowdfund payment, donations, fund distribution |
| 9 | **Insurance/Lending** | Premium payment, loan repayment, claims |
| 10 | **Marketing/Points** | Coupons, points redemption, red envelopes, discounts |
| 11 | **Rental Service** | Deposit, rent payment, lease renewal, move-out settlement |
| 12 | **Ticketing/Booking** | Ticket purchase, seat selection, ticket refund |

### Identification Strategy

```
FOR each scenario (1-12):
    Search routes, controllers, models, and services for scenario-specific keywords
    Check database tables and schema for matching structures
    Look for related configuration entries
    Assign confidence: high (clear match) / medium (partial signals) / low (inferred)
    IF confidence >= medium: mark as identified
```

### Keyword Patterns by Scenario

- **E-Commerce**: `cart`, `checkout`, `order`, `product`, `sku`, `inventory`, `stock`
- **Subscription**: `subscribe`, `membership`, `plan`, `recurring`, `renew`, `tier`
- **Multi-Sided Platform**: `commission`, `merchant`, `settle`, `split`, `vendor`
- **Prepayment**: `deposit`, `down_payment`, `balance_due`, `reservation`, `booking_fee`
- **Financial**: `transfer`, `withdraw`, `recharge`, `topup`, `wallet`, `balance`
- **Content/Gaming**: `virtual_currency`, `coin`, `gem`, `in_app`, `item_purchase`
- **Enterprise B2B**: `enterprise`, `corporate`, `invoice`, `batch_pay`, `approval_flow`
- **Crowdfunding**: `crowdfund`, `campaign`, `pledge`, `donate`, `backer`
- **Insurance/Lending**: `premium`, `policy`, `loan`, `repay`, `claim`, `interest`
- **Marketing/Points**: `coupon`, `points`, `redeem`, `voucher`, `red_packet`, `discount`
- **Rental**: `rent`, `lease`, `deposit_refund`, `move_out`, `rental_period`
- **Ticketing**: `ticket`, `seat`, `venue`, `event`, `booking`, `refund_ticket`

---

## Phase 1b: Per-Scenario Business Analysis

For **each identified scenario**, perform deep analysis.

### Analysis Requirements per Scenario

1. **Business Design Intent**: What business problem does this payment flow solve?
2. **Core Workflow**: Complete payment flow from user initiation to completion
3. **Key Decision Points**: Where does the code make business judgments or logic branches?

### Workflow Code Extraction

For each workflow, trace through all 6 layers:

| Layer | What to Extract |
|-------|----------------|
| **Entry** | Route/controller definition, HTTP method, URL pattern |
| **Global** | Filters, middleware, interceptors, AOP aspects, decorators (with execution order) |
| **Business** | Core logic steps in order -- amount calculation, validation, state transitions |
| **Data** | Database operations, SQL/ORM queries, transaction boundaries |
| **Config** | Related configuration parameters (timeouts, limits, keys) |
| **External** | Payment gateway calls, third-party API integrations |

### Cross-Language Awareness

| Language | Key Patterns to Track |
|----------|----------------------|
| Java | `@Transactional`, `@RequestMapping`, Filter chain, AOP, `application.yml` |
| PHP | Middleware, Event Listeners, Service Providers, `.env`/`config/` |
| Python | Middleware, decorators, signals, `settings.py`/`config.py` |
| Go | Middleware chain, `defer` rollback, YAML/JSON/TOML config |
| Node.js | Middleware stack, hooks, plugins, `config.js`/`.env` |

### Code Extraction Principles

- Keep code snippets complete with 3-5 lines of context
- Record accurate `file_path` and `line_range`
- Preserve original formatting and comments
- If a snippet exceeds 50 lines, extract the core logic and note the omission

---

## Output Schema

Write to `{output_dir}/payment/business_logic.json`.

The payment module wraps all analysis inside `identified_scenarios[]`:

```json
{
  "project_language": "Java|PHP|Python|Golang|Node.js",
  "project_framework": "Spring Boot|Laravel|Django|Gin|Express|...",
  "identified_scenarios": [
    {
      "scenario_id": 1,
      "scenario_name": "E-Commerce",
      "confidence": "high|medium|low",
      "business_intent": "Description of the business problem this scenario solves",
      "core_workflow": "High-level flow summary from initiation to completion",
      "workflows": [
        {
          "workflow_id": "pay_ecommerce_001",
          "workflow_name": "Order Checkout Payment",
          "description": "Triggered when user confirms checkout...",
          "entry_point": {
            "type": "route|controller|handler",
            "file_path": "relative/path/to/file",
            "code_snippet": "...",
            "line_range": "45-67"
          },
          "global_components": [
            {
              "component_type": "filter|middleware|interceptor|aop|decorator",
              "name": "PaymentAuthMiddleware",
              "file_path": "...",
              "code_snippet": "...",
              "execution_order": 1,
              "purpose": "JWT authentication for payment endpoints"
            }
          ],
          "business_logic": [
            {
              "step_id": 1,
              "step_name": "Calculate order total",
              "file_path": "...",
              "function_name": "calculateTotal",
              "code_snippet": "...",
              "line_range": "100-120",
              "key_operations": ["price lookup", "quantity validation", "discount application"],
              "calls_external": false,
              "has_transaction": true
            }
          ],
          "data_operations": [
            {
              "operation_type": "select|insert|update|delete",
              "table_name": "orders",
              "file_path": "...",
              "code_snippet": "...",
              "line_range": "130-135"
            }
          ],
          "configurations": [
            {
              "config_key": "payment.timeout",
              "config_value": "30",
              "file_path": "config/payment.yml",
              "usage_context": "Payment gateway request timeout in seconds"
            }
          ],
          "external_calls": [
            {
              "service_name": "Stripe API",
              "api_endpoint": "/v1/charges",
              "file_path": "...",
              "code_snippet": "...",
              "purpose": "Create payment charge"
            }
          ]
        }
      ]
    }
  ]
}
```

---

## Validation Checklist

Before completing Step 1, verify:

- [ ] All 12 scenario types were evaluated (even if most are not present)
- [ ] Each identified scenario has at least one workflow
- [ ] Every workflow traces through all 6 layers (entry, global, business, data, config, external)
- [ ] Code snippets include accurate file paths and line ranges
- [ ] Global components (middleware, filters) are tracked with execution order
- [ ] Transaction boundaries are identified
- [ ] External payment gateway calls are captured
- [ ] The `identified_scenarios[]` wrapper is present in the output JSON
