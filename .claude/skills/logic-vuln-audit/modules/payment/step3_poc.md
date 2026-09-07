# Payment PoC Generation Guide

Generate executable Python PoC scripts for each confirmed payment vulnerability.

**Input**: `payment/vulnerability_analysis.json` from Step 2

---

## Payment-Specific Exploitation Patterns

Payment vulnerabilities have distinct exploit patterns. Use the matching pattern for each vulnerability type.

### Pattern 1: Amount Tampering

Intercept and modify price/amount/quantity parameters in the payment request.

```
1. Create a normal order (observe legitimate request)
2. Replay the request with modified amount/price/quantity fields
3. Verify order is created with tampered values
4. Complete payment at the reduced amount
5. Confirm goods/service delivered at original value
```

**Key parameters to tamper**: `price`, `amount`, `total`, `quantity`, `unit_price`, `discount_amount`
**Negative test**: Set quantity to 0, -1, or 0.001; set price to 0.01

### Pattern 2: Race Condition / Double-Spend

Send concurrent requests to exploit TOCTOU windows in balance or inventory checks.

```
1. Identify the vulnerable endpoint (balance deduction, inventory decrement)
2. Prepare N identical requests with valid auth tokens
3. Send all N requests simultaneously (threading/async)
4. Check if total deductions exceed the available balance/stock
5. Verify N successes where only 1 should have succeeded
```

**Targets**: Balance withdrawal, inventory purchase, coupon redemption, points redemption
**Tool**: Python `threading` or `asyncio` with `aiohttp` for concurrent requests

### Pattern 3: Callback Forgery

Forge payment gateway callback to mark orders as paid without actual payment.

```
1. Create an order (obtain order_id and expected callback format)
2. Construct a fake callback payload matching the gateway format
3. If signature is required, test with empty/known-weak signatures
4. Send the forged callback to the notification URL
5. Check if the order status changed to "paid"
```

**Bypass techniques**: Missing signature check, predictable signing keys, unsigned fields, IP whitelist bypass via headers

### Pattern 4: Coupon/Discount Stacking Abuse

Stack multiple discount mechanisms to achieve below-cost or negative-price purchases.

```
1. Add item to cart at normal price
2. Apply coupon code (discount A)
3. Apply points redemption (discount B)
4. Apply promotional discount (discount C)
5. Verify final price: check if total < 0 or unreasonably low
6. Complete payment at the stacked discount price
```

**Targets**: Coupon + points, coupon + coupon, membership discount + promotion, referral credit + coupon

### Pattern 5: State Machine Bypass

Skip required payment steps by directly calling downstream endpoints.

```
1. Identify the expected state flow (e.g., cart -> order -> pay -> confirm)
2. Skip intermediate steps (e.g., call confirm endpoint directly)
3. Modify order status parameters if exposed
4. Check if business logic proceeds without payment verification
```

### Pattern 6: Privilege Escalation / IDOR

Access or modify other users' payment resources via parameter manipulation.

```
1. Authenticate as User A
2. Create an order as User A (get order_id)
3. Authenticate as User B
4. Attempt to view/modify/cancel User A's order using the order_id
5. Attempt to withdraw from User A's wallet by changing user_id param
```

---

## PoC Code Requirements

### Structure

Every PoC must:
- Use Python `requests` library
- Be self-contained and directly executable
- Accept configurable parameters (target URL, credentials)
- Include step-by-step comments explaining each action
- Print clear output indicating success or failure
- Handle HTTP errors and unexpected responses gracefully

### For Race Condition PoCs

```python
import threading
import requests

results = []

def exploit(session, url, payload):
    resp = session.post(url, json=payload)
    results.append(resp.json())

threads = [threading.Thread(target=exploit, args=(s, url, payload)) for _ in range(N)]
for t in threads: t.start()
for t in threads: t.join()
# Analyze: count successes -- if > 1, race condition confirmed
```

### For Callback Forgery PoCs

```python
# Construct the callback payload matching the gateway format
callback_payload = {
    "order_id": target_order_id,
    "amount": "0.01",
    "status": "SUCCESS",
    "sign": ""  # Empty or forged signature
}
resp = requests.post(callback_url, json=callback_payload)
# Verify: check order status changed to paid
```

---

## Output

Write PoC files to `{output_dir}/payment/pocs/`:
- `poc_{ID}.json` — structured exploitation data
- `poc_{ID}.py` — executable Python script inheriting `BasePoC`

Schema: see `@reference/JSON_SCHEMAS.md` § poc_output.

> **Note**: Do NOT produce exploit chain files here. Exploit chains are handled by the Chain & Reporter Agent in Phase 5.

---

## PoC Priority

| Severity | PoC Required? |
|----------|--------------|
| Critical | MUST generate |
| High | MUST generate |
| Medium | RECOMMENDED -- generate if clearly exploitable |
| Low | OPTIONAL |

## Accuracy Requirements

- HTTP requests must match actual endpoint paths, methods, and parameter names from `business_logic.json`
- Data flow between steps must follow the real business logic sequence
- Do not assume endpoints or parameters that were not found in the code analysis
- Base all PoC logic on the vulnerabilities confirmed in Step 2
