from .audit import AuditLog
from .ledger import Ledger
from .models import Agent
from .payment import MockPaymentGateway
from .policy import PolicyEngine
from .world import World

class Dail:
    def __init__(self):
        self.audit = AuditLog()
        self.ledger = Ledger(self.audit)
        self.policy = PolicyEngine()
        self.payment = MockPaymentGateway(self.ledger, self.audit)
        self.world = World()
        self.agents = {}

    def create_agent(self, agent):
        if agent.id in self.agents:
            raise ValueError("agent already exists")
        self.agents[agent.id] = agent
        self.ledger.balances[agent.id] = agent.balance
        self.audit.append("agent.created", agent.model_dump())
        return agent

    def deposit(self, agent_id, amount, provider, idem):
        self._agent(agent_id)
        return self.payment.deposit(agent_id, amount, idem)

    def pay(self, agent_id, merchant, amount, idem, reason="", approved=False):
        agent = self._agent(agent_id)
        ok, reason_code = self.policy.authorize_payment(agent, amount, approved)
        self.audit.append("policy.payment", {
            "agent": agent_id, "amount": amount, "result": reason_code, "reason": reason
        })
        if not ok:
            raise PermissionError(reason_code)
        tx = self.payment.charge(agent_id, merchant, amount, idem)
        agent.balance = self.ledger.balances[agent_id]
        return tx

    def tool(self, agent_id, tool, args, estimated_cost=0):
        agent = self._agent(agent_id)
        ok, reason = self.policy.authorize_tool(agent, tool, estimated_cost)
        self.audit.append("policy.tool", {"agent": agent_id, "tool": tool, "result": reason})
        if not ok:
            raise PermissionError(reason)
        return {"tool": tool, "result": {"status": "simulated", "args": args}}

    def tick(self):
        event = self.world.step()
        self.audit.append("world.tick", event)
        return event

    def _agent(self, agent_id):
        if agent_id not in self.agents:
            raise KeyError("agent not found")
        return self.agents[agent_id]
