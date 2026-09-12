from pydantic import BaseModel, Field
from typing import Literal

class Agent(BaseModel):
    id: str
    name: str
    goal: str
    balance: int = 0
    spending_limit: int = 10000
    approval_limit: int = 2500
    status: Literal["active", "paused", "disabled"] = "active"

class Transaction(BaseModel):
    id: str
    kind: str
    from_account: str
    to_account: str
    amount: int = Field(gt=0)
    currency: str = "DAIL"
    idempotency_key: str
    status: Literal["posted", "rejected", "refunded"] = "posted"

class ToolRequest(BaseModel):
    agent_id: str
    tool: str
    args: dict = {}
    estimated_cost: int = 0

class DepositRequest(BaseModel):
    agent_id: str
    amount: int = Field(gt=0)
    provider: str = "mock"
    idempotency_key: str

class PaymentRequest(BaseModel):
    agent_id: str
    merchant: str
    amount: int = Field(gt=0)
    idempotency_key: str
    reason: str = ""
    approved: bool = False
