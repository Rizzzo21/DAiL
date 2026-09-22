from collections import defaultdict
from datetime import datetime, timezone
from sqlalchemy import text
from .models import Transaction

class LedgerError(Exception): pass
class Ledger:
    def __init__(self,audit,core=None):
        self.audit=audit; self.core=core; self.balances=defaultdict(int); self.transactions={}; self.idempotency={}
        if core and core.engine: self._load()
    def _load(self):
        with self.core.engine.begin() as c:
            rows=c.execute(text('SELECT id,kind,from_account,to_account,amount,currency,idempotency_key,status FROM dail_transactions')).mappings().all()
            for r in rows:
                tx=Transaction(**dict(r)); self.transactions[tx.id]=tx; self.idempotency[tx.idempotency_key]=tx.id
            rows=c.execute(text('SELECT id,balance FROM dail_agents')).all()
            for aid,b in rows: self.balances[aid]=b
    def _persist_tx(self,tx):
        if not self.core or not self.core.engine:return
        with self.core.engine.begin() as c:
            c.execute(text('''INSERT INTO dail_transactions(id,kind,from_account,to_account,amount,currency,idempotency_key,status,created_at)
            VALUES(:id,:kind,:f,:t,:a,:cur,:idem,:s,:now) ON CONFLICT(id) DO NOTHING'''),{'id':tx.id,'kind':tx.kind,'f':tx.from_account,'t':tx.to_account,'a':tx.amount,'cur':tx.currency,'idem':tx.idempotency_key,'s':tx.status,'now':datetime.now(timezone.utc).isoformat()})
            if tx.to_account in self.balances: c.execute(text('UPDATE dail_agents SET balance=:b,updated_at=:now WHERE id=:id'),{'b':self.balances[tx.to_account],'id':tx.to_account,'now':datetime.now(timezone.utc).isoformat()})
            if tx.from_account in self.balances: c.execute(text('UPDATE dail_agents SET balance=:b,updated_at=:now WHERE id=:id'),{'b':self.balances[tx.from_account],'id':tx.from_account,'now':datetime.now(timezone.utc).isoformat()})
    def credit(self,account,amount,kind='credit',idem=None):
        if amount<=0: raise LedgerError('amount must be positive')
        if idem and idem in self.idempotency:return self.transactions[self.idempotency[idem]]
        txid=f'tx_{len(self.transactions)+1:06d}'
        tx=Transaction(id=txid,kind=kind,from_account='SYSTEM',to_account=account,amount=amount,idempotency_key=idem or txid)
        self.balances[account]+=amount; self.transactions[txid]=tx; self.idempotency[tx.idempotency_key]=txid; self._persist_tx(tx); self.audit.append('ledger.credit',tx.model_dump()); return tx
    def transfer(self,source,destination,amount,kind='payment',idem=None):
        if amount<=0: raise LedgerError('amount must be positive')
        if idem and idem in self.idempotency:return self.transactions[self.idempotency[idem]]
        if self.balances[source]<amount: raise LedgerError('insufficient funds')
        txid=f'tx_{len(self.transactions)+1:06d}'; tx=Transaction(id=txid,kind=kind,from_account=source,to_account=destination,amount=amount,idempotency_key=idem or txid)
        self.balances[source]-=amount; self.balances[destination]+=amount; self.transactions[txid]=tx; self.idempotency[tx.idempotency_key]=txid; self._persist_tx(tx); self.audit.append('ledger.transfer',tx.model_dump()); return tx
    def refund(self,txid):
        if txid not in self.transactions: raise KeyError(txid)
        original=self.transactions[txid]
        if original.status=='refunded':return original
        if self.balances[original.to_account] < original.amount: raise LedgerError('refund would exceed available balance; account requires manual review')
        self.transfer(original.to_account,original.from_account,original.amount,kind='refund',idem=f'refund:{txid}')
        original.status='refunded'
        if self.core and self.core.engine:
            with self.core.engine.begin() as c:c.execute(text('UPDATE dail_transactions SET status=\'refunded\' WHERE id=:id'),{'id':txid})
        self.audit.append('ledger.refund',{'txid':txid});return original
