# DAiL Production Ready Package

This package is the consolidated production launch layer. It is designed so the final live-money switch is gated behind persistent storage and agent authentication.

## Final Render environment
Set these only in Render Environment Variables (never in GitHub or chat):

- `DATABASE_URL` = persistent PostgreSQL connection string
- `DAIL_REAL_PAYMENTS=true`
- `DAIL_REQUIRE_AUTH=true`
- `STRIPE_SECRET_KEY=sk_live_...`
- `STRIPE_WEBHOOK_SECRET=whsec_...`
- `DAIL_PER_USD=<published conversion rate>`

## Stripe webhook
Point Stripe to:
`https://dail-1.onrender.com/payments/webhook`

Enable at minimum:
- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `charge.refunded`

Use Stripe's signature verification; never trust a client success redirect as proof of payment.

## What is now persistent
- Agent identities and account balances
- Ledger transactions and idempotency keys
- Agent API keys (hashed at rest)
- Stripe payment records

## Safety gates
Real payment readiness requires all of the following:
- PostgreSQL configured and reachable
- Stripe live secret and webhook secret configured
- `DAIL_REAL_PAYMENTS=true`
- `DAIL_REQUIRE_AUTH=true`
- Persistent ledger active
- Agent API authentication active

## Important launch checks before collecting customer money
1. Run a Stripe test-mode checkout end-to-end.
2. Confirm webhook credits exactly once.
3. Restart/redeploy Render and confirm the balance remains.
4. Test a refund and confirm the corresponding DAiL reversal or manual-review path.
5. Verify your published DAIL/USD rate, terms, refund policy, and business/tax/compliance requirements.
6. Only then replace Stripe test credentials with live credentials.

The code does not claim that a Stripe payment has been completed merely because a browser returned to the success URL.
