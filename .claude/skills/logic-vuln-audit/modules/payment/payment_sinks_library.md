# Payment SINK Definition Library

Complete catalog of payment business logic vulnerability SINK points.

**Structure**:
- Part 1: 12 Business-Scenario-Specific SINK Categories (42 SINKs)
- Part 2: 6 Cross-Scenario Universal SINK Categories (21 SINKs)
- **Total: 63 SINK definitions**

---

# Part 1: Business-Scenario-Specific SINKs

---

## Category 1: E-Commerce (5 SINKs)

### SINK-EC-01: Order Amount Tampering
**Severity**: Critical
**Description**: Attacker tampers with product price, quantity, or discount parameters to complete payment at a lower price or for free.

**Detection Checkpoints**:
- When creating an order or adding to cart, is the client-submitted product price used directly for calculation instead of being re-queried from the database? (HIGHEST PRIORITY)
- When creating an order or adding to cart, can the client-submitted quantity be set to a float or negative number, manipulating the final settlement price? (HIGHEST PRIORITY)
- Does the order total rely on frontend-calculated results rather than backend recalculation?
- Can coupon amounts or discount ratios be controlled by the frontend?
- Is there negative and float validation on quantity parameters?
- At settlement time, are product price and inventory validity re-verified?

**Risk**: Attacker purchases goods for 0.01 or free by modifying price/quantity in transit.

### SINK-EC-02: Duplicate Payment
**Severity**: High
**Description**: The same order can be paid multiple times, causing repeated deductions from the user or multiple shipments from the merchant.

**Detection Checkpoints**:
- Is the order status check performed before the transaction begins?
- Is there a race condition between order status update and payment operation?
- Does the payment interface lack idempotency design (e.g., unique transaction ID validation)?
- Are distributed locks or database row locks used to prevent concurrent payment?
- Does the payment callback handler have replay prevention?

**Risk**: User is charged multiple times, or merchant ships goods repeatedly for one order.

### SINK-EC-03: Inventory Oversell
**Severity**: Critical
**Description**: Concurrent orders cause actual sales to exceed available inventory.

**Detection Checkpoints**:
- Does inventory deduction use atomic operations (e.g., `UPDATE SET stock = stock - ? WHERE stock >= ?`)?
- Are inventory check and deduction within the same transaction?
- Is there a race window between querying inventory and deducting it?
- Is there a timeout release mechanism between pre-deduction and actual deduction?
- When canceling orders, does inventory rollback correctly handle concurrency?

**Risk**: More items sold than physically available, causing fulfillment failures and financial loss.

### SINK-EC-04: Discount Stacking Abuse
**Severity**: High
**Description**: Illegally stacking coupons, points, and discounts to achieve excessive discounts or even negative-price purchases.

**Detection Checkpoints**:
- Are there mutual exclusion rules checking for multiple discount types?
- Is the total discount amount capped (cannot exceed original product price)?
- Is the final payment amount validated to not be negative or zero?
- Are coupon usage conditions (minimum spend, category restrictions) strictly verified server-side?
- Can the discount calculation order be manipulated to produce different results?

**Risk**: Attacker combines discounts to buy items at negative price, generating credits instead of charges.

### SINK-EC-05: Order Status Tampering
**Severity**: Critical
**Description**: Attacker tampers with order status to skip payment and proceed to shipment, or changes a paid order to unpaid.

**Detection Checkpoints**:
- Does the order status modification interface have strict permission control?
- Does status transition follow state machine rules (e.g., unpaid cannot jump to shipped)?
- Can users directly modify critical order fields (status, amount, shipping address) via API?
- Does the payment callback verify order ownership and current status?
- Is there a horizontal privilege escalation issue where modifying order IDs accesses others' orders?

**Risk**: Attacker receives goods without payment, or reverses completed transactions.

---

## Category 2: Subscription/Membership (3 SINKs)

### SINK-SUB-01: Subscription Period Tampering
**Severity**: Critical
**Description**: Attacker modifies subscription period parameters to purchase annual membership at monthly price.

**Detection Checkpoints**:
- Is the subscription plan price-to-period mapping hardcoded or in server-side configuration?
- Is the frontend-submitted subscription period parameter used directly?
- Is price calculation based on plan ID queried from database rather than frontend parameters?
- Is there consistency validation between subscription duration and payment amount?

**Risk**: Attacker gets a year of premium service for the price of one month.

### SINK-SUB-02: Auto-Renewal Bypass
**Severity**: High
**Description**: User bypasses auto-renewal charges after consuming services, or attacker maliciously triggers another user's renewal.

**Detection Checkpoints**:
- Does the auto-renewal task check user account balance or payment method validity?
- After renewal failure, is service immediately stopped (vs. delayed or continued)?
- Does user cancellation of renewal take effect immediately, preventing charges within a timing window?
- Does the renewal task have idempotency protection to prevent duplicate billing?

**Risk**: Users consume services without paying for renewal, or are fraudulently double-charged.

### SINK-SUB-03: Membership Downgrade Privilege Retention
**Severity**: High
**Description**: User retains premium permissions after downgrading membership, or bypasses payment during upgrade flow.

**Detection Checkpoints**:
- Does membership level change immediately update the permission cache (Redis/Session)?
- Does permission checking query the latest membership status each time rather than relying on stale cache?
- Does membership upgrade verify payment completion status?
- Is there a race condition between upgrade request and payment callback?

**Risk**: User enjoys premium features indefinitely after downgrading, or upgrades without paying.

---

## Category 3: Multi-Sided Platform (4 SINKs)

### SINK-MSP-01: Platform Commission Bypass
**Severity**: Critical
**Description**: Merchant or service provider bypasses platform commission by tampering with order amounts, receiving full payment directly.

**Detection Checkpoints**:
- Is the commission rate read from platform configuration rather than merchant-supplied?
- Is commission calculated on the platform backend rather than relying on merchant-side calculation?
- Is there consistency validation between order amount and actual payment amount?
- At settlement time, is commission recalculated rather than using the cached value from order creation?

**Risk**: Merchants avoid platform fees, causing direct revenue loss to the platform.

### SINK-MSP-02: Split Payment Amount Tampering
**Severity**: Critical
**Description**: Attacker tampers with split payment ratios or amounts, causing incorrect fund distribution.

**Detection Checkpoints**:
- Is the split ratio hardcoded or read from secure configuration?
- Does the sum of all parties' split amounts equal the order total?
- Can split parameters be modified by the frontend or merchant side?
- Does the split interface have permission control (only platform can invoke)?
- Does multi-party splitting have atomicity guarantees (all succeed or all fail)?

**Risk**: Funds distributed incorrectly, potentially stealing other parties' share.

### SINK-MSP-03: Merchant Withdrawal Privilege Escalation
**Severity**: Critical
**Description**: Merchant withdraws another account's balance, or withdrawal amount exceeds available balance.

**Detection Checkpoints**:
- Does the withdrawal interface verify the withdrawal account belongs to the currently logged-in merchant?
- Is the withdrawal amount validated to not exceed available balance (order amount - frozen amount - already withdrawn)?
- Is available balance calculated in real-time rather than relying on cache?
- Is there a race condition in concurrent withdrawals causing negative balance?
- Does the withdrawal operation use database transactions and row locks?

**Risk**: Merchants steal funds from other accounts or overdraw their own balance.

### SINK-MSP-04: Order Ownership Tampering
**Severity**: High
**Description**: By modifying order ownership, another merchant's order revenue is transferred to the attacker's account.

**Detection Checkpoints**:
- When creating orders, is the merchant ID assigned by the system rather than user-submitted?
- Can the owning merchant be modified before order completion?
- At settlement time, is order ownership validity and consistency verified?
- Is it possible to transfer order ownership by modifying order parameters?

**Risk**: Attacker redirects another merchant's revenue to their own settlement account.

---

## Category 4: Prepayment/Reservation (3 SINKs)

### SINK-PRE-01: Deposit Payment Bypass
**Severity**: Critical
**Description**: User skips deposit payment and proceeds directly to final payment, or tampers with deposit amount.

**Detection Checkpoints**:
- Before final payment, is the deposit paid status verified?
- Is the deposit amount calculated server-side rather than from frontend parameters?
- Is the final payment amount calculated based on the actual paid deposit (not the supposed amount)?
- Is there association validation between deposit order and final payment order?
- Can deposit be bypassed by modifying order status?

**Risk**: User avoids deposit requirement, potentially getting goods/services without proper payment commitment.

### SINK-PRE-02: Final Payment Calculation Error
**Severity**: High
**Description**: Final payment amount is calculated incorrectly, causing the user to underpay or overpay.

**Detection Checkpoints**:
- Is final payment = total price - actual deposit paid calculated correctly?
- Is there consistency validation between product price at deposit time and at final payment time?
- Does final payment allow coupons that reduce total below the deposit already paid?
- How are deposit orders handled when prices adjust (increase or decrease)?
- Is the final payment amount validated with a floor check (cannot be negative or zero)?

**Risk**: Financial discrepancies in the deposit-to-final-payment flow, causing revenue loss.

### SINK-PRE-03: Reservation Time Tampering
**Severity**: High
**Description**: User modifies reservation time to bypass peak pricing or occupy another user's reservation slot.

**Detection Checkpoints**:
- Can reservation time be modified after order creation?
- When modifying reservation time, is the price recalculated (e.g., peak period markup)?
- Is reservation time conflict detection performed within a transaction?
- Is there a vulnerability where time modification does not trigger price update?

**Risk**: User books peak-hour services at off-peak prices or blocks other users' reservations.

---

## Category 5: Financial Payment (4 SINKs)

### SINK-FIN-01: Transfer Amount Tampering
**Severity**: Critical
**Description**: Attacker tampers with transfer amount or recipient account to execute unauthorized transfers.

**Detection Checkpoints**:
- Is the transfer amount validated for reasonableness (minimum, maximum, precision)?
- Is the transfer amount re-confirmed against user balance (preventing frontend tampering)?
- Is the recipient account verified for existence and validity?
- Does the transfer operation require secondary confirmation (password or verification code)?
- Does the transfer interface have request signature anti-tampering protection?

**Risk**: Unauthorized fund transfers draining user accounts.

### SINK-FIN-02: Balance Concurrency Exploitation
**Severity**: Critical
**Description**: Concurrent transfers, withdrawals, or top-ups cause balance calculation errors, resulting in negative balance or phantom balance increase.

**Detection Checkpoints**:
- Does balance update use database row locks or optimistic locking?
- Does balance deduction use atomic operations (`UPDATE SET balance = balance - ? WHERE balance >= ?`)?
- Can concurrent withdrawals cause negative balance?
- Are top-up credit and deduction operations within the same transaction?
- Is there a race window between balance query and balance update?

**Risk**: Attacker multiplies funds through concurrent operations or creates negative balances.

### SINK-FIN-03: Withdrawal Limit Bypass
**Severity**: High
**Description**: Bypassing per-transaction or daily withdrawal limits through multiple small withdrawals or parameter tampering.

**Detection Checkpoints**:
- Is the per-transaction withdrawal limit validated server-side?
- Is the daily withdrawal total accumulated and validated?
- Can the withdrawal limit configuration be tampered with by the user?
- Is it possible to bypass limits through multiple accounts or multiple devices?

**Risk**: User extracts funds beyond intended limits, potentially enabling money laundering.

### SINK-FIN-04: Top-Up Callback Forgery
**Severity**: Critical
**Description**: Attacker forges payment gateway callback to credit balance without actual payment.

**Detection Checkpoints**:
- Does the top-up callback verify the signature (using platform secret key)?
- Is the callback source IP within the payment gateway whitelist?
- Are callback parameters (order ID, amount, status) validated for consistency against local order?
- Is there replay attack protection (timestamp/nonce validation)?
- Is the credited amount based on the gateway return value rather than the local order amount?

**Risk**: Attacker credits unlimited funds to their account without paying.

---

## Category 6: Content/Gaming (4 SINKs)

### SINK-CG-01: Virtual Currency Recharge Ratio Tampering
**Severity**: Critical
**Description**: Attacker modifies recharge ratio to obtain large amounts of virtual currency at low cost.

**Detection Checkpoints**:
- Is the recharge ratio (real currency to virtual currency) hardcoded or read from secure configuration?
- Is the frontend-submitted virtual currency quantity used directly?
- Is the virtual currency credit amount calculated server-side based on actual payment?
- Are recharge tiers and bonus ratios verified server-side?
- Is there strict consistency validation between recharge order amount and virtual currency quantity?

**Risk**: Attacker gets millions of virtual coins for the price of the minimum recharge.

### SINK-CG-02: Item Purchase Negative Quantity
**Severity**: Critical
**Description**: Purchasing with negative quantity grants items while increasing virtual currency balance.

**Detection Checkpoints**:
- Is the purchase quantity parameter validated as a positive integer?
- Does a negative quantity cause virtual currency balance to increase rather than decrease?
- Is there overflow validation on total price calculation for batch purchases?
- Does virtual currency deduction use safe math operations?
- After purchase completion, is virtual currency balance re-verified to ensure it did not increase?

**Risk**: Attacker generates unlimited virtual currency by "selling" items they never owned.

### SINK-CG-03: In-App Purchase Verification Bypass
**Severity**: Critical
**Description**: User obtains in-app purchase items without actual payment (e.g., by cracking the client).

**Detection Checkpoints**:
- Are in-app purchase receipts (e.g., Apple/Google payment receipts) verified server-side?
- Is the official API called to verify payment receipt authenticity?
- Can payment receipts be reused (are used receipts recorded)?
- Is the client-submitted purchase success status trustworthy?
- Are in-app item grants and payment verification within the same transaction?

**Risk**: Users get premium content/items without paying, causing direct revenue loss.

### SINK-CG-04: Game Currency Trading Duplication
**Severity**: High
**Description**: Exploiting the trading system or gift function to duplicate game currency.

**Detection Checkpoints**:
- Are player-to-player transfers/trades subject to cooldown and frequency limits?
- Are both parties' currency changes within the same transaction (atomicity)?
- Can trade rollback or cancellation result in one party receiving currency while the other is not debited?
- Is there risk control for abnormal trading behavior (e.g., many alt accounts transferring to one main)?

**Risk**: Infinite currency generation through trading exploits, destroying game economy.

---

## Category 7: Enterprise B2B (3 SINKs)

### SINK-B2B-01: Enterprise Account Authorization Bypass
**Severity**: Critical
**Description**: Unauthorized employee operates the enterprise payment account, or escalates privilege to approve high-value payments.

**Detection Checkpoints**:
- Does payment operation verify the operator's role and permissions within the enterprise?
- Do high-value payments require multi-level approval workflow?
- Can the approval workflow be skipped or can approval status be tampered?
- Are payment limits enforced based on employee permission level?
- Are departed employee account permissions immediately revoked?

**Risk**: Unauthorized employees execute high-value payments, causing corporate financial loss.

### SINK-B2B-02: Batch Payment Amount Tampering
**Severity**: Critical
**Description**: During batch payment, individual or multiple payment record amounts or recipient accounts are tampered with.

**Detection Checkpoints**:
- Are batch payment details re-verified server-side (amounts, accounts, count)?
- Can the frontend batch payment list be tampered with?
- Is there consistency validation between batch payment total and detail sum?
- If a single payment fails, does it affect the entire batch (transaction control)?
- Are there upper limits on batch payment count and total amount?

**Risk**: Funds diverted to attacker-controlled accounts in bulk.

### SINK-B2B-03: Enterprise Balance Overdraft
**Severity**: High
**Description**: Enterprise account completes payment despite insufficient balance, causing bad debt.

**Detection Checkpoints**:
- Is enterprise account balance verified sufficient before payment?
- Is credit limit usage strictly controlled with approval?
- Can concurrent payments cause overdraft (atomicity of balance check and deduction)?
- Are orders correctly handled when balance is insufficient (cancel or pending top-up)?
- Is service immediately suspended for overdue enterprises?

**Risk**: Enterprise accumulates debt beyond credit limits, creating unrecoverable bad debt.

---

## Category 8: Crowdfunding/Donation (2 SINKs)

### SINK-CF-01: Crowdfunding Amount Tampering
**Severity**: Critical
**Description**: Attacker modifies pledge amount to receive high-tier rewards at a low-tier price.

**Detection Checkpoints**:
- Is the pledge-to-reward tier mapping verified server-side?
- Is there consistency validation between frontend-submitted amount and actual payment?
- Is the reward tier determined server-side based on actual payment amount?
- Is crowdfunding tier inventory (limited rewards) correctly decremented?
- Is the amount re-verified against the reward tier in the payment callback?

**Risk**: Attacker backs at $1 and receives the $1000 reward tier.

### SINK-CF-02: Crowdfunding Goal Verification Bypass
**Severity**: High
**Description**: Project execution or reward distribution begins before reaching the funding goal, or refunds are still allowed after success.

**Detection Checkpoints**:
- Does project execution verify that crowdfunding amount has reached the target?
- Is the crowdfunding amount tally real-time and accurate (excluding refunds)?
- Does crowdfunding failure automatically trigger refund process?
- After crowdfunding success, are large refunds prohibited?
- Can the project creator tamper with crowdfunding progress?

**Risk**: Failed projects distribute rewards, or successful projects are drained by post-success refunds.

---

## Category 9: Insurance/Lending (4 SINKs)

### SINK-IL-01: Premium Calculation Tampering
**Severity**: Critical
**Description**: Attacker modifies insured value, coverage period, or other parameters to obtain high coverage at low premium.

**Detection Checkpoints**:
- Is the premium calculation formula hardcoded server-side?
- Does the insured value require supporting documentation?
- Are coverage period, coverage amount, and insurance type validated server-side for reasonableness?
- Is the premium calculated server-side based on a risk assessment model?
- Are user-submitted parameters used directly in premium calculation?

**Risk**: Attacker gets massive coverage for minimal premium, creating outsized liability for the insurer.

### SINK-IL-02: Claim Amount Privilege Escalation
**Severity**: Critical
**Description**: User claims an amount exceeding coverage, or files duplicate claims for the same incident.

**Detection Checkpoints**:
- Is the claim amount validated to not exceed the policy's agreed coverage?
- Can the same incident be claimed multiple times?
- Is the claim application verified to be within the policy validity period?
- Are claim conditions (deductible, claim ratio) correctly calculated?
- Can the claim approval workflow be bypassed?

**Risk**: Insurer pays out far more than the policy entitles, causing direct financial loss.

### SINK-IL-03: Loan Amount Tampering
**Severity**: Critical
**Description**: Attacker modifies loan amount, interest rate, or repayment period to obtain an excessive loan.

**Detection Checkpoints**:
- Is the loan amount calculated server-side based on user credit score?
- Is the user-submitted loan amount validated to not exceed the approved credit limit?
- Is the interest rate determined server-side based on platform rules and user tier?
- Are repayment period and repayment method validated for reasonableness?
- Are loan contract terms tamper-proof?

**Risk**: Attacker obtains loans far exceeding their creditworthiness, creating default risk.

### SINK-IL-04: Repayment Amount Calculation Error
**Severity**: High
**Description**: Repayment amount calculation error causes user to underpay or overpay, affecting interest and principal settlement.

**Detection Checkpoints**:
- Is repayment amount (principal + interest) calculation correct?
- For early repayment, is interest calculated based on actual days elapsed?
- For overdue repayment, is penalty interest correctly accumulated?
- For partial repayment, is principal/interest allocation correct?
- Is the repayment received amount validated for consistency with the amount due?

**Risk**: Systematic calculation errors cause lender losses or borrower overcharges.

---

## Category 10: Marketing/Points (4 SINKs)

### SINK-MKT-01: Points Farming
**Severity**: High
**Description**: Maliciously farming points through repeated operations, scripting, or bot abuse.

**Detection Checkpoints**:
- Are points-earning actions rate-limited (e.g., daily check-in once only)?
- Does points issuance have idempotency protection (prevent duplicate awards)?
- Is there risk control for abnormal points-earning behavior (e.g., high-frequency operations in short time)?
- Does new user registration bonus have anti-bot protection?
- Does referral-for-points verify the referred friend is a real person?

**Risk**: Attacker farms massive points that can be redeemed for real value.

### SINK-MKT-02: Coupon Reuse
**Severity**: Critical
**Description**: The same coupon is used multiple times, or a used coupon is reset to unused status.

**Detection Checkpoints**:
- Is coupon usage status atomically updated at order payment time?
- Is there race condition protection for concurrent use of the same coupon?
- When an order is canceled, is the coupon correctly returned?
- Is the coupon usage record associated with the order?
- Is coupon validity re-confirmed in the payment callback?

**Risk**: A single high-value coupon used unlimited times, causing unlimited discount losses.

### SINK-MKT-03: Points Redemption Ratio Tampering
**Severity**: Critical
**Description**: Attacker modifies points redemption ratio to redeem high-value goods with minimal points.

**Detection Checkpoints**:
- Is the redemption ratio configured server-side and tamper-proof?
- Is the frontend-submitted redemption quantity used directly?
- Are points consumed during redemption calculated server-side based on item value?
- Are points deduction and item delivery within the same transaction?
- When points balance is insufficient, is the redemption request correctly rejected?

**Risk**: Attacker redeems premium goods for nearly zero points.

### SINK-MKT-04: Red Envelope Amount Tampering
**Severity**: Critical
**Description**: Attacker modifies red envelope amount, or claims another user's red envelope.

**Detection Checkpoints**:
- Is the red envelope amount randomly generated server-side or from configuration?
- Is the frontend-submitted red envelope amount parameter used?
- Does red envelope claiming verify user eligibility (e.g., new user only)?
- Can the same user claim the same red envelope repeatedly?
- Is there consistency validation between total red envelope amount and claimed amounts?

**Risk**: Attacker claims arbitrarily large red envelopes or steals others' red envelopes.

---

## Category 11: Rental Service (3 SINKs)

### SINK-RNT-01: Deposit Refund Condition Bypass
**Severity**: High
**Description**: User obtains full deposit refund despite item damage or loss.

**Detection Checkpoints**:
- Does deposit refund verify item return status?
- Is there an audit process for item damage assessment?
- Is deposit deduction calculated based on degree of damage?
- Can the user self-modify the return status to trigger refund?
- Is the deposit automatically forfeited when overdue and unreturned?

**Risk**: Users get deposits back despite damaging or losing rented items.

### SINK-RNT-02: Rent Calculation Error
**Severity**: High
**Description**: Rent calculation error causes user to underpay or overpay rent.

**Detection Checkpoints**:
- Is rent calculated based on actual rental days/hours?
- Can rental duration be tampered with by the user?
- For early return, is rent calculated based on actual usage time?
- For overdue extension, is rent correctly accumulated?
- Is the per-unit rent price dynamically adjusted by time period (e.g., peak hours)?

**Risk**: Systematic rent miscalculation causes revenue leakage.

### SINK-RNT-03: Lease Renewal Status Tampering
**Severity**: High
**Description**: User continues using rented item without paying renewal fee.

**Detection Checkpoints**:
- Does renewal operation verify that previous rental period is fully paid?
- When renewal payment fails, is rental status updated?
- When rental expires, is item control immediately revoked (e.g., smart lock remote lock)?
- For automatic renewal, is user balance verified sufficient?

**Risk**: Users use rental items indefinitely without payment.

---

## Category 12: Ticketing/Booking (3 SINKs)

### SINK-TKT-01: Seat Double-Booking
**Severity**: Critical
**Description**: The same seat is booked by multiple users, causing conflicts and disputes.

**Detection Checkpoints**:
- Does seat booking use database row locks or distributed locks?
- Are seat status check and update within the same transaction?
- Is there race condition protection for concurrent booking requests?
- Does seat booking have a timeout auto-release mechanism?
- Before booking confirmation, is seat availability re-verified?

**Risk**: Multiple customers arrive to find the same seat, causing service disruption and reputation damage.

### SINK-TKT-02: Ticket Price Tampering
**Severity**: Critical
**Description**: Attacker modifies ticket price parameters to purchase premium tickets at low prices.

**Detection Checkpoints**:
- Is the ticket price calculated server-side based on seat class, showtime, and timing?
- Is the frontend-submitted price parameter used directly?
- Is dynamic pricing (e.g., peak period markup) correctly implemented?
- Do ticket discounts and promotions have eligibility verification?
- Does the payment callback verify that the actual payment matches the ticket price?

**Risk**: Attacker buys VIP tickets at general admission prices.

### SINK-TKT-03: Refund Rule Bypass
**Severity**: High
**Description**: User obtains refund without meeting refund conditions, or uses the ticket after refunding.

**Detection Checkpoints**:
- Does refund verify time restrictions (e.g., 24 hours before the event)?
- Is the refund handling fee correctly calculated per policy?
- Are already-used tickets (e.g., already scanned) prohibited from refunding?
- After refund, is ticket status immediately updated to refunded?
- After refund of an e-ticket, is the QR code invalidated?

**Risk**: Users attend events for free by refunding after use, or bypass refund deadlines.

---

# Part 2: Cross-Scenario Universal SINKs

These apply to **ALL** identified payment scenarios.

---

## Universal Category 1: Payment Callback Verification (4 SINKs)

### SINK-CB-01: Callback Signature Verification Bypass
**Severity**: Critical
**Description**: Attacker forges payment gateway callback, bypassing signature verification to complete orders without actual payment.

**Detection Checkpoints**:
- Is the callback signature verified using the platform secret key (not merchant ID or other predictable info)?
- Is the signature algorithm sufficiently secure (avoid weak algorithms like plain MD5)?
- Does signature verification failure result in rejecting the callback?
- Is there signature verification code that is commented out or conditionally bypassed?
- Is the signing key hardcoded in the codebase where it could leak?

**Risk**: Attacker marks any order as paid without spending a cent.

### SINK-CB-02: Callback Replay Attack
**Severity**: High
**Description**: Attacker replays historical callback requests, causing duplicate top-ups or shipments.

**Detection Checkpoints**:
- Does callback processing verify the order's current status (reject if already processed)?
- Does the callback request have a unique identifier (transaction ID) and is it recorded as processed?
- Is a nonce or timestamp used to prevent replay attacks?
- Does the same callback request have idempotency protection?
- In a distributed environment, does callback deduplication use a global lock?

**Risk**: A single legitimate payment triggers unlimited fulfillment/credit operations.

### SINK-CB-03: Callback Parameter Tampering
**Severity**: Critical
**Description**: Attacker modifies callback parameters (order ID, amount, status) to bypass business logic.

**Detection Checkpoints**:
- Does the callback order ID match a local order?
- Is the callback amount strictly consistent with the order amount (to the cent)?
- Is payment status only trusted from the payment gateway return value?
- Do all callback parameters participate in signature verification?
- Is the order's owning user verified (prevent User A's order being paid by User B)?

**Risk**: Attacker swaps order IDs or amounts to get expensive items credited to cheap payments.

### SINK-CB-04: Callback Source Verification Failure
**Severity**: High
**Description**: Any source can invoke the callback interface, forging payment results.

**Detection Checkpoints**:
- Is the callback source IP within the payment gateway's whitelist?
- Does the callback interface have replay prevention (timestamp/nonce)?
- Is the callback interface directly accessible from the public internet?
- Is there an alerting mechanism for abnormal callback sources?

**Risk**: Attacker calls the callback endpoint directly from any IP to forge payment confirmations.

---

## Universal Category 2: Order State Machine (3 SINKs)

### SINK-SM-01: State Transition Violation
**Severity**: Critical
**Description**: Order status can be arbitrarily jumped, bypassing normal business flow.

**Detection Checkpoints**:
- Does state transition follow predefined state machine rules?
- Can users directly modify order status (should only be system-internal)?
- Can an unpaid order directly become shipped/completed?
- Does the status modification interface have strict permission control?
- Are illegal state transition requests intercepted by risk control?

**Risk**: Orders skip payment and proceed directly to fulfillment.

### SINK-SM-02: Concurrent State Conflict
**Severity**: High
**Description**: Concurrent modification of order status causes data inconsistency.

**Detection Checkpoints**:
- Does status modification use database row locks or optimistic locking?
- Is there a race window between checking status and updating status?
- Is there conflict handling for concurrent order cancellation and payment callback?
- Are version numbers or timestamps used to prevent concurrent overwrites?
- Do status changes publish events to notify other modules to synchronize?

**Risk**: Order stuck in inconsistent state, or concurrent cancel+pay leads to paid-but-cancelled orders.

### SINK-SM-03: State Rollback Exploit
**Severity**: High
**Description**: Abnormal order status rollback causes business logic confusion.

**Detection Checkpoints**:
- Can a paid order be rolled back to unpaid status?
- When rolling back status, are associated operations (funds, points) synchronously reversed?
- Is status rollback performed within a transaction for atomicity?
- Is it clearly defined which statuses allow rollback and which prohibit it?

**Risk**: Attacker rolls back paid orders to unpaid, then receives a refund while keeping the goods.

---

## Universal Category 3: Amount Calculation & Precision (4 SINKs)

### SINK-AMT-01: Floating Point Precision Loss
**Severity**: High
**Description**: Using floating point numbers for monetary calculations causes precision errors that accumulate and can be exploited for arbitrage.

**Detection Checkpoints**:
- Are amounts stored or calculated using float/double types instead of integer or fixed-point?
- Are dedicated currency types used (e.g., Java BigDecimal)?
- Do consecutive floating point operations accumulate errors?
- Does amount comparison use exact equality (==) instead of tolerance-based comparison?
- Is there overflow risk for large amount calculations?

**Risk**: Attacker exploits rounding differences across many small transactions for profit.

### SINK-AMT-02: Unit Conversion Error
**Severity**: Medium
**Description**: Precision loss or logic error during conversion between dollars/cents (or yuan/fen) or between integer/decimal.

**Detection Checkpoints**:
- Does dollars-to-cents conversion use multiplication (*100) rather than string processing?
- Does cents-to-dollars conversion use division (/100) and correctly handle remainders?
- Does unit conversion have explicit rounding rules?
- Are the units consistent between API parameters and database storage?

**Risk**: Systematic rounding errors cause financial discrepancies at scale.

### SINK-AMT-03: Integer Overflow
**Severity**: High
**Description**: Amount calculation exceeds data type range causing overflow.

**Detection Checkpoints**:
- Is there overflow validation on large amount multiplication?
- Does quantity * unit_price check that the result is within a reasonable range?
- Is the integer type large enough (int vs long)?
- Does overflow throw an exception rather than silently wrapping?
- Are safe math operation libraries used?

**Risk**: Overflow wraps a huge charge into a tiny or negative number.

### SINK-AMT-04: Amount Validation Missing
**Severity**: Critical
**Description**: Critical monetary calculations lack validation, allowing abnormal amounts to pass through.

**Detection Checkpoints**:
- Is the final payment amount validated to be non-negative?
- Is the post-discount amount validated to be >= 0?
- Is the refund amount validated to not exceed the original payment?
- Are abnormal amounts (e.g., $0.01 for a $10,000 item) caught by risk control?
- Are there secondary validation checks at critical amount nodes?

**Risk**: Zero or near-zero payments processed for high-value orders.

---

## Universal Category 4: Concurrency/Duplicate Control (4 SINKs)

### SINK-CC-01: Idempotency Missing
**Severity**: Critical
**Description**: The same request executed multiple times causes duplicate charges, shipments, or credits.

**Detection Checkpoints**:
- Do critical operations have a unique identifier (order ID, transaction ID, idempotency token)?
- Is the unique identifier validated as unused before processing?
- Is the idempotency check performed before the transaction begins?
- Is the idempotency record persisted (not just in-memory cache)?
- In a distributed environment, is the idempotency check globally effective?

**Risk**: Network retries or intentional replays cause duplicate financial operations.

### SINK-CC-02: Distributed Lock Missing
**Severity**: High
**Description**: Concurrent operations in a distributed environment cause data inconsistency.

**Detection Checkpoints**:
- Are critical resources (account balance, inventory) protected by distributed locks?
- Do distributed locks have timeout to prevent deadlocks?
- Is there retry or friendly error on lock acquisition failure?
- Is a reliable distributed lock implementation used (Redis, Zookeeper)?

**Risk**: Concurrent requests bypass each other's checks, causing double-spend or oversell.

### SINK-CC-03: Database Lock Missing
**Severity**: Critical
**Description**: Database concurrent operations cause dirty reads, phantom reads, or non-repeatable reads.

**Detection Checkpoints**:
- Do critical queries use row locks (`SELECT ... FOR UPDATE`)?
- Is there a race window between query and update?
- Do update operations use atomic operations (`UPDATE SET x = x + ?`)?
- Are deadlock exceptions correctly handled?
- Is optimistic locking (version numbers) correctly implemented?

**Risk**: Balance/inventory values corrupted by concurrent access.

### SINK-CC-04: Timing Race Condition
**Severity**: High
**Description**: Multiple operations executed out of order cause business logic anomalies.

**Detection Checkpoints**:
- Are critical operation sequences within the same transaction?
- Do state-dependent operations check prerequisite states?
- Do concurrent modifications use version number control?
- Is there a time window between check and execution?
- Do distributed transactions guarantee eventual consistency?

**Risk**: Payment processed after cancellation, or refund issued before payment confirms.

---

## Universal Category 5: Authorization & Privilege (3 SINKs)

### SINK-AUTH-01: Horizontal Privilege Escalation (IDOR)
**Severity**: Critical
**Description**: User can access or operate on another user's orders, accounts, or other resources.

**Detection Checkpoints**:
- Do order query/modification operations verify the order belongs to the current user?
- Is the user ID obtained from the session rather than frontend parameters?
- Is it possible to enumerate other users' order IDs?
- Are order numbers predictable (sequential numbers)?
- Do interfaces verify resource ownership?

**Risk**: Attacker views, modifies, or cancels any user's orders and payment records.

### SINK-AUTH-02: Vertical Privilege Escalation
**Severity**: High
**Description**: Regular user executes administrator operations.

**Detection Checkpoints**:
- Do sensitive operations (refund, settlement, config changes) verify admin privileges?
- Are role permissions strictly controlled server-side?
- Are there hidden admin interfaces without authentication?
- Do API interfaces have a unified permission interceptor?

**Risk**: Regular user triggers refunds, modifies pricing, or accesses admin settlement functions.

### SINK-AUTH-03: Interface Authentication Missing
**Severity**: High
**Description**: Payment-related interfaces can be accessed anonymously without authentication.

**Detection Checkpoints**:
- Do all payment interfaces require login?
- Is JWT/Token validity and expiration verified?
- Are there unauthenticated sensitive interfaces?
- Can authentication be bypassed by modifying request headers?

**Risk**: Anonymous attacker creates orders, triggers payments, or accesses financial data.

---

## Universal Category 6: Data Validation (3 SINKs)

### SINK-DV-01: Parameter Tampering
**Severity**: Critical
**Description**: Critical frontend-submitted parameters are used directly by the backend without validation.

**Detection Checkpoints**:
- Is product price queried from the database rather than from frontend parameters?
- Are identity fields (user ID, merchant ID) obtained from the session?
- Is the payment amount recalculated server-side rather than trusting the frontend?
- Can order status be modified by the frontend?
- Are discount amounts and ratios verified server-side?

**Risk**: Attacker controls any parameter the server fails to independently verify.

### SINK-DV-02: Input Validation Missing
**Severity**: Medium
**Description**: Lack of input validation allows abnormal data to enter the system.

**Detection Checkpoints**:
- Are numeric parameters validated for range (max/min)?
- Are string parameters validated for length and format?
- Are enum parameters validated to be within allowed values?
- Are special characters filtered to prevent injection?
- Are required parameters enforced?

**Risk**: Malformed input causes unexpected behavior in downstream payment processing.

### SINK-DV-03: Business Logic Validation Missing
**Severity**: High
**Description**: Missing business rule validation allows unreasonable operations to pass through.

**Detection Checkpoints**:
- Is inventory sufficiency validated?
- Is account balance sufficiency validated?
- Is coupon validity validated (expiration, usage conditions)?
- Does order status allow the current operation?
- Are business rules centrally validated server-side?

**Risk**: Operations proceed despite violating business constraints, causing financial inconsistencies.

---

# Quick Reference: SINK Count Summary

| Category | ID Range | Count |
|----------|----------|-------|
| 1. E-Commerce | SINK-EC-01 to EC-05 | 5 |
| 2. Subscription | SINK-SUB-01 to SUB-03 | 3 |
| 3. Multi-Sided Platform | SINK-MSP-01 to MSP-04 | 4 |
| 4. Prepayment | SINK-PRE-01 to PRE-03 | 3 |
| 5. Financial | SINK-FIN-01 to FIN-04 | 4 |
| 6. Content/Gaming | SINK-CG-01 to CG-04 | 4 |
| 7. Enterprise B2B | SINK-B2B-01 to B2B-03 | 3 |
| 8. Crowdfunding | SINK-CF-01 to CF-02 | 2 |
| 9. Insurance/Lending | SINK-IL-01 to IL-04 | 4 |
| 10. Marketing/Points | SINK-MKT-01 to MKT-04 | 4 |
| 11. Rental Service | SINK-RNT-01 to RNT-03 | 3 |
| 12. Ticketing/Booking | SINK-TKT-01 to TKT-03 | 3 |
| **Scenario subtotal** | | **42** |
| U1. Callback Verification | SINK-CB-01 to CB-04 | 4 |
| U2. Order State Machine | SINK-SM-01 to SM-03 | 3 |
| U3. Amount Calculation | SINK-AMT-01 to AMT-04 | 4 |
| U4. Concurrency Control | SINK-CC-01 to CC-04 | 4 |
| U5. Authorization | SINK-AUTH-01 to AUTH-03 | 3 |
| U6. Data Validation | SINK-DV-01 to DV-03 | 3 |
| **Universal subtotal** | | **21** |
| **Grand total** | | **63** |
