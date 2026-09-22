"""Production payment boundary for DAiL.

Stripe is the external payment rail. A verified webhook is the only path that
marks a payment paid and credits DAIL. Payment records live in PostgreSQL when
production mode is enabled; SQLite is used only for local development.
"""
import os, threading
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
try:
    import stripe
except ImportError:  # pragma: no cover
    stripe = None

class ProductionPayments:
    def __init__(self, dail):
        self.dail = dail
        self.enabled = os.getenv("DAIL_REAL_PAYMENTS", "false").lower() == "true"
        self.stripe_secret = os.getenv("STRIPE_SECRET_KEY", "")
        self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
        self.database_url = os.getenv("DATABASE_URL", "")
        self.dail_per_usd = int(os.getenv("DAIL_PER_USD", "1"))
        self._lock = threading.Lock()
        self.engine = None
        if self.database_url:
            self.engine = create_engine(self.database_url, pool_pre_ping=True)
            self._init_db()
        if stripe and self.stripe_secret:
            stripe.api_key = self.stripe_secret

    @property
    def ready(self):
        return bool(self.enabled and stripe and self.stripe_secret and self.webhook_secret and self.database_url and self.engine and self.dail.core.engine and self.dail_per_usd > 0 and os.getenv('DAIL_REQUIRE_AUTH','false').lower() == 'true')

    def status(self):
        return {"provider":"stripe","production_enabled":self.enabled,"production_ready":self.ready,"real_money":self.ready,"persistent_database_configured":bool(self.database_url),"dail_per_usd":self.dail_per_usd}

    def _init_db(self):
        with self.engine.begin() as c:
            c.execute(text("""CREATE TABLE IF NOT EXISTS dail_payments (
                id VARCHAR(255) PRIMARY KEY, agent_id VARCHAR(255) NOT NULL,
                session_id VARCHAR(255) UNIQUE NOT NULL, usd_cents INTEGER NOT NULL,
                dail_amount INTEGER NOT NULL, status VARCHAR(32) NOT NULL,
                created_at VARCHAR(64) NOT NULL, paid_at VARCHAR(64)
            )"""))

    def _require_ready(self):
        if not self.ready:
            raise RuntimeError("real_payments_not_ready: configure DAIL_REAL_PAYMENTS, Stripe secrets, DATABASE_URL, and dependencies")

    def create_checkout(self, agent_id, usd_cents, success_url, cancel_url):
        self._require_ready()
        if agent_id not in self.dail.agents: raise KeyError("agent not found")
        if usd_cents < 100 or usd_cents > 1000000: raise ValueError("amount must be between $1 and $10,000")
        dail_amount=(usd_cents*self.dail_per_usd)//100
        if dail_amount<=0: raise ValueError("amount produces zero DAIL")
        session=stripe.checkout.Session.create(mode="payment",payment_method_types=["card"],line_items=[{"price_data":{"currency":"usd","product_data":{"name":"DAiL credits"},"unit_amount":usd_cents},"quantity":1}],success_url=success_url,cancel_url=cancel_url,metadata={"agent_id":agent_id,"dail_amount":str(dail_amount)})
        with self.engine.begin() as c:
            c.execute(text("INSERT INTO dail_payments (id,agent_id,session_id,usd_cents,dail_amount,status,created_at) VALUES (:id,:agent,:sid,:usd,:dail,'pending',:created)"),{"id":session.id,"agent":agent_id,"sid":session.id,"usd":usd_cents,"dail":dail_amount,"created":datetime.now(timezone.utc).isoformat()})
        return {"checkout_url":session.url,"session_id":session.id,"usd_cents":usd_cents,"dail_amount":dail_amount,"status":"pending"}

    def webhook(self, payload, signature):
        self._require_ready()
        try: event=stripe.Webhook.construct_event(payload,signature,self.webhook_secret)
        except Exception as e: raise ValueError(f"invalid webhook: {e}")
        if event["type"] not in ("checkout.session.completed","checkout.session.async_payment_succeeded","charge.refunded"):
            return {"received":True,"handled":False,"event":event["type"]}
        if event["type"] == "charge.refunded":
            charge=event["data"]["object"]
            sid=(charge.get("metadata") or {}).get("checkout_session_id") or (charge.get("payment_intent") or "")
            with self.engine.begin() as c:
                row=c.execute(text("SELECT agent_id,status FROM dail_payments WHERE session_id=:sid"),{"sid":sid}).fetchone()
            if not row: return {"received":True,"handled":False,"reason":"refund_without_checkout_mapping"}
            agent_id,status=row
            if status == "refunded": return {"received":True,"handled":True,"duplicate":True,"session_id":sid}
            txid=(charge.get("metadata") or {}).get("dail_transaction_id")
            if txid:
                tx=self.dail.ledger.refund(txid)
                with self.engine.begin() as c:c.execute(text("UPDATE dail_payments SET status='refunded' WHERE session_id=:sid"),{"sid":sid})
                return {"received":True,"handled":True,"session_id":sid,"transaction_id":tx.id,"status":"refunded"}
            return {"received":True,"handled":False,"reason":"missing_dail_transaction_mapping"}
        session=event["data"]["object"]; sid=session["id"]
        with self._lock, self.engine.begin() as c:
            row=c.execute(text("SELECT agent_id,dail_amount,status FROM dail_payments WHERE session_id=:sid FOR UPDATE"),{"sid":sid}).fetchone()
            if not row: raise ValueError("unknown checkout session")
            agent_id,dail_amount,status=row
            if status=="paid": return {"received":True,"handled":True,"duplicate":True,"session_id":sid}
            c.execute(text("UPDATE dail_payments SET status='paid',paid_at=:paid WHERE session_id=:sid"),{"paid":datetime.now(timezone.utc).isoformat(),"sid":sid})
        tx=self.dail.ledger.credit(agent_id,int(dail_amount),kind="stripe_deposit",idem=f"stripe:{sid}")
        try:
            stripe.PaymentIntent.modify(session.get("payment_intent"), metadata={"checkout_session_id":sid,"dail_transaction_id":tx.id}) if session.get("payment_intent") else None
        except Exception:
            pass
        self.dail.agents[agent_id].balance=self.dail.ledger.balances[agent_id]
        self.dail.audit.append("payment.stripe_verified",{"session_id":sid,"agent_id":agent_id,"amount_dail":dail_amount,"transaction":tx.id})
        return {"received":True,"handled":True,"duplicate":False,"session_id":sid,"transaction_id":tx.id}
