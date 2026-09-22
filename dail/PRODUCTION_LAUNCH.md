# DAiL Production Launch

This package adds the public launch page and a Stripe production payment boundary.

## What is protected
- A payment is credited only after a verified Stripe webhook.
- Checkout amounts are bounded to $1–$10,000 per payment.
- Checkout sessions carry the DAiL agent ID in Stripe metadata.
- Webhook processing is idempotent by Stripe session ID.
- Production mode refuses to start unless a persistent `DATABASE_URL` and Stripe secrets are configured.
- No secret belongs in GitHub source code.

## Required Render environment variables
- `DAIL_REAL_PAYMENTS=true`
- `STRIPE_SECRET_KEY=sk_live_...`
- `STRIPE_WEBHOOK_SECRET=whsec_...`
- `DATABASE_URL=<persistent PostgreSQL URL>`
- `DAIL_PER_USD=1` (example: $1 USD = 1 DAIL; choose and publish the actual rate before launch)

Install the added dependency from `requirements.txt`.

## Stripe setup
Create a Stripe Checkout webhook endpoint at:
`https://YOUR-DAIL-DOMAIN/payments/webhook`

Subscribe at minimum to:
- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`

Use Stripe test mode first. Switch to live keys only after the production database, agent persistence, reconciliation, refund/dispute handling, authentication, rate limits, and monitoring are in place.

## Important architecture note
The existing DAiL world ledger is still in-memory. This package deliberately does **not** claim the entire DAiL economy is production-custodial. The Stripe layer persists payment records and verifies webhooks, but the world ledger itself must be migrated to persistent storage before real customer funds are accepted at scale.
