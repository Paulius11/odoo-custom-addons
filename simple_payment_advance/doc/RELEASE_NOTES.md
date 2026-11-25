## Module simple_payment_advance

#### 19.11.2026
#### Version 19.0.1.0.2
#### BUG FIX
- The advance accounts setting now shows on Invoicing too, not only with full accounting features.
- A draft advance saved before the accounts were set now posts on the advance account.
- An advance needs a customer or vendor, and must be money received from a customer or paid to a vendor; a payout no longer counts as an open advance.
- Invoices and bills in a foreign currency no longer show Apply Advance.

#### 19.11.2026
#### Version 19.0.1.0.1
#### UPDATE
- Renamed from `account_payment_advance`, a name already taken on the Odoo Apps Store. A database with the old module installed must uninstall it and install this one.
