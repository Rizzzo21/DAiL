from fastapi import FastAPI, HTTPException
from .models import Agent, DepositRequest, PaymentRequest, ToolRequest
from .service import Dail
from .ledger import LedgerError

app = FastAPI(title="DAiL Test API", version="0.1.0-test")
dail = Dail()

@app.get("/health")
def health():
    return {"ok": True, "environment": "test", "real_payments": False}

@app.post("/agents")
def create_agent(agent: Agent):
    try:
        return dail.create_agent(agent)
    except ValueError as e:
        raise HTTPException(409, str(e))

@app.get("/agents")
def agents():
    return list(dail.agents.values())

@app.post("/deposits")
def deposit(req: DepositRequest):
    try:
        return dail.deposit(req.agent_id, req.amount, req.provider, req.idempotency_key)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except LedgerError as e:
        raise HTTPException(400, str(e))

@app.post("/payments")
def payment(req: PaymentRequest):
    try:
        return dail.pay(req.agent_id, req.merchant, req.amount,
                        req.idempotency_key, req.reason, req.approved)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except LedgerError as e:
        raise HTTPException(400, str(e))

@app.post("/tools")
def tool(req: ToolRequest):
    try:
        return dail.tool(req.agent_id, req.tool, req.args, req.estimated_cost)
    except KeyError as e:
        raise HTTPException(404, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))

@app.post("/world/tick")
def tick():
    return dail.tick()

@app.get("/audit/verify")
def verify_audit():
    return {"valid": dail.audit.verify(), "events": len(dail.audit.events)}

@app.get("/ledger/{agent_id}")
def balance(agent_id):
    if agent_id not in dail.agents:
        raise HTTPException(404, "agent not found")
    return {"agent_id": agent_id, "balance": dail.ledger.balances[agent_id], "currency": "DAIL"}
