from fastapi.testclient import TestClient
from dail.api import app, dail

client = TestClient(app)

def setup_function():
    dail.__init__()

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["real_payments"] is False

def test_end_to_end():
    assert client.post("/agents", json={
        "id":"a1","name":"Test Agent","goal":"trade","balance":0,
        "spending_limit":5000,"approval_limit":2500
    }).status_code == 200
    assert client.post("/deposits", json={
        "agent_id":"a1","amount":10000,"provider":"mock","idempotency_key":"d1"
    }).status_code == 200
    r = client.post("/payments", json={
        "agent_id":"a1","merchant":"demo","amount":1000,
        "idempotency_key":"p1","reason":"test purchase","approved":False
    })
    assert r.status_code == 200
    assert client.get("/ledger/a1").json()["balance"] == 9000
    assert client.get("/audit/verify").json()["valid"] is True
