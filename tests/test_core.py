import pytest
from dail.models import Agent
from dail.service import Dail

def make():
    x = Dail()
    x.create_agent(Agent(id="a1", name="Ada", goal="learn", balance=10000,
                         spending_limit=5000, approval_limit=2500))
    return x

def test_deposit_and_balance():
    x = make()
    x.deposit("a1", 5000, "mock", "dep-1")
    assert x.ledger.balances["a1"] == 15000
    assert x.audit.verify()

def test_payment():
    x = make()
    tx = x.pay("a1", "market", 1000, "pay-1", "food")
    assert tx.status == "posted"
    assert x.ledger.balances["a1"] == 9000

def test_approval_required():
    x = make()
    with pytest.raises(PermissionError, match="human_approval_required"):
        x.pay("a1", "market", 3000, "pay-approval")

def test_approval_allows():
    x = make()
    x.pay("a1", "market", 3000, "pay-approved", approved=True)
    assert x.ledger.balances["a1"] == 7000

def test_spending_limit():
    x = make()
    with pytest.raises(PermissionError, match="spending_limit_exceeded"):
        x.pay("a1", "market", 6000, "pay-limit")

def test_insufficient_funds():
    x = Dail()
    x.create_agent(Agent(id="poor", name="Poor", goal="test", balance=1000,
                         spending_limit=50000, approval_limit=2500))
    with pytest.raises(Exception, match="insufficient funds"):
        x.pay("poor", "market", 20000, "pay-funds", approved=True)

def test_idempotency():
    x = make()
    first = x.deposit("a1", 5000, "mock", "same-key")
    second = x.deposit("a1", 5000, "mock", "same-key")
    assert first.id == second.id
    assert x.ledger.balances["a1"] == 15000

def test_refund():
    x = make()
    tx = x.pay("a1", "market", 1000, "pay-refund")
    x.ledger.refund(tx.id)
    assert x.ledger.balances["a1"] == 10000

def test_tool_allowlist():
    x = make()
    assert x.tool("a1", "world.read", {})["result"]["status"] == "simulated"

def test_tool_denied():
    x = make()
    with pytest.raises(PermissionError, match="tool_not_allowlisted"):
        x.tool("a1", "shell.exec", {})

def test_pause_blocks():
    x = make()
    x.agents["a1"].status = "paused"
    with pytest.raises(PermissionError, match="agent_not_active"):
        x.pay("a1", "market", 100, "pause-pay")

def test_world_tick_and_audit():
    x = make()
    x.tick()
    assert x.world.tick == 1
    assert x.audit.verify()
