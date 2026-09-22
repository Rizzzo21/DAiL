import os, hashlib, secrets
from datetime import datetime, timezone
from sqlalchemy import create_engine, text

class PersistentCore:
    def __init__(self, audit):
        self.audit=audit
        self.url=os.getenv('DATABASE_URL','')
        self.engine=create_engine(self.url,pool_pre_ping=True) if self.url else None
        if self.engine: self.init_db()
    def init_db(self):
        with self.engine.begin() as c:
            c.execute(text('''CREATE TABLE IF NOT EXISTS dail_agents (
                id VARCHAR(255) PRIMARY KEY, name VARCHAR(255) NOT NULL, goal TEXT NOT NULL,
                balance BIGINT NOT NULL DEFAULT 0, spending_limit BIGINT NOT NULL,
                approval_limit BIGINT NOT NULL, status VARCHAR(32) NOT NULL, created_at VARCHAR(64) NOT NULL,
                updated_at VARCHAR(64) NOT NULL)'''))
            c.execute(text('''CREATE TABLE IF NOT EXISTS dail_transactions (
                id VARCHAR(255) PRIMARY KEY, kind VARCHAR(64) NOT NULL, from_account VARCHAR(255) NOT NULL,
                to_account VARCHAR(255) NOT NULL, amount BIGINT NOT NULL, currency VARCHAR(8) NOT NULL,
                idempotency_key VARCHAR(255) UNIQUE NOT NULL, status VARCHAR(32) NOT NULL,
                created_at VARCHAR(64) NOT NULL)'''))
            c.execute(text('''CREATE TABLE IF NOT EXISTS dail_api_keys (
                key_id VARCHAR(64) PRIMARY KEY, agent_id VARCHAR(255) NOT NULL, key_hash VARCHAR(128) UNIQUE NOT NULL,
                created_at VARCHAR(64) NOT NULL, revoked_at VARCHAR(64))'''))
            c.execute(text('CREATE INDEX IF NOT EXISTS idx_dail_tx_idem ON dail_transactions(idempotency_key)'))
            c.execute(text('CREATE INDEX IF NOT EXISTS idx_dail_keys_hash ON dail_api_keys(key_hash)'))
    def agent_rows(self):
        if not self.engine: return []
        with self.engine.begin() as c:
            return c.execute(text('SELECT id,name,goal,balance,spending_limit,approval_limit,status FROM dail_agents')).mappings().all()
    def save_agent(self,a):
        now=datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as c:
            c.execute(text('''INSERT INTO dail_agents(id,name,goal,balance,spending_limit,approval_limit,status,created_at,updated_at)
            VALUES(:id,:name,:goal,:balance,:sl,:al,:status,:now,:now)
            ON CONFLICT(id) DO UPDATE SET name=:name,goal=:goal,balance=:balance,spending_limit=:sl,approval_limit=:al,status=:status,updated_at=:now'''),
            {'id':a.id,'name':a.name,'goal':a.goal,'balance':a.balance,'sl':a.spending_limit,'al':a.approval_limit,'status':a.status,'now':now})
    def save_balance(self,agent_id,balance):
        with self.engine.begin() as c: c.execute(text('UPDATE dail_agents SET balance=:b,updated_at=:now WHERE id=:id'),{'b':balance,'id':agent_id,'now':datetime.now(timezone.utc).isoformat()})
    def create_key(self,agent_id):
        raw='dail_'+secrets.token_urlsafe(32); kid=secrets.token_hex(8); h=hashlib.sha256(raw.encode()).hexdigest()
        with self.engine.begin() as c: c.execute(text('INSERT INTO dail_api_keys(key_id,agent_id,key_hash,created_at) VALUES(:kid,:aid,:h,:now)'),{'kid':kid,'aid':agent_id,'h':h,'now':datetime.now(timezone.utc).isoformat()})
        return {'key_id':kid,'api_key':raw,'agent_id':agent_id}
    def authenticate(self,raw):
        if not raw or not self.engine: return None
        h=hashlib.sha256(raw.encode()).hexdigest()
        with self.engine.begin() as c:
            r=c.execute(text('SELECT agent_id FROM dail_api_keys WHERE key_hash=:h AND revoked_at IS NULL'),{'h':h}).fetchone()
            return r[0] if r else None
