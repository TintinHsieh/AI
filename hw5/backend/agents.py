"""PydanticAI multi-agent operations workflow for Campus Customs."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastmcp import Client
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from .audit import record_event
from .db import connect


PROJECT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_DIR / ".mcp.json"
for env_path in (PROJECT_DIR / ".env", PROJECT_DIR.parent / ".env"):
    load_dotenv(env_path, override=False)

SPECIALISTS = ("Inventory", "Accounting", "Facilities", "Customer Service")


class BossPlan(BaseModel):
    first_specialist: Literal["Inventory", "Accounting", "Facilities", "Customer Service"]
    additional_specialists: list[Literal["Inventory", "Accounting", "Facilities", "Customer Service"]] = Field(default_factory=list)
    rationale: str
    questions_to_answer: list[str] = Field(default_factory=list)


class SpecialistReport(BaseModel):
    specialist: str
    finding: str
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str
    should_prepare_payment: bool = False
    requires_human_approval: bool = False
    confidence: float = Field(ge=0, le=1)


class BossDecision(BaseModel):
    status: Literal["resolved", "pending_approval", "blocked", "needs_information"]
    decision: str
    rationale: str
    next_action: str
    should_prepare_payment: bool = False
    payment_reason: str | None = None
    specialists_used: list[str] = Field(default_factory=list)


class WorkflowResult(BaseModel):
    run_id: str
    ticket_id: int
    status: str
    plan: BossPlan | None = None
    specialist_reports: list[SpecialistReport] = Field(default_factory=list)
    decision: BossDecision | None = None
    payment_request: dict[str, Any] | None = None
    error: str | None = None


class MCPGateway:
    """One protocol client shared by a single workflow run."""

    def __init__(self, *, run_id: str, ticket_id: int):
        self.run_id = run_id
        self.ticket_id = ticket_id
        self.client: Client | None = None

    async def __aenter__(self) -> "MCPGateway":
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        self.client = Client(config)
        await self.client.__aenter__()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.client is not None:
            await self.client.__aexit__(exc_type, exc, tb)

    async def call(self, agent: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.client is None:
            raise RuntimeError("MCP gateway is not connected")
        record_event(run_id=self.run_id, ticket_id=self.ticket_id, agent=agent, event_type="tool_call", details={"tool": tool_name, "arguments": arguments})
        result = await self.client.call_tool(tool_name, arguments)
        payload = result.structured_content or {"ok": False, "error": {"code": "empty_tool_result", "message": "MCP returned no structured content."}}
        record_event(run_id=self.run_id, ticket_id=self.ticket_id, agent=agent, event_type="tool_result", details={"tool": tool_name, "result": payload, "protocol_error": result.is_error})
        if result.is_error:
            raise RuntimeError(f"MCP tool {tool_name} returned a protocol error")
        return payload


class AgentDeps(BaseModel):
    """PydanticAI dependency envelope for specialist tool calls."""

    run_id: str
    ticket_id: int
    agent_name: str
    gateway: Any

    class Config:
        arbitrary_types_allowed = True


def model() -> OpenAIResponsesModel:
    """Build the required Portkey OpenAI-compatible model without exposing credentials."""

    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is not configured in a local environment file")
    model_name = os.getenv("MODEL_NAME") or "gpt-6-luna"
    if model_name != "gpt-6-luna":
        raise RuntimeError("MODEL_NAME must remain gpt-6-luna for this assignment")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.portkey.ai/v1",
        default_headers={"x-portkey-provider": "openai"},
    )
    provider = OpenAIProvider(openai_client=client)
    # gpt-6-luna requires tool calls through the Responses API when reasoning
    # is enabled; OpenAIResponsesModel maps Portkey's OpenAI-compatible
    # /v1/responses endpoint and preserves structured PydanticAI outputs.
    return OpenAIResponsesModel(model_name, provider=provider)


def _tool_functions(agent: Agent[AgentDeps, SpecialistReport], allowed_tools: set[str]) -> None:
    """Register only the MCP tools that belong to this specialist's remit."""

    if "inspect_ticket" in allowed_tools:
        @agent.tool
        async def inspect_ticket(ctx: RunContext[AgentDeps], ticket_id: int) -> dict[str, Any]:
            return await ctx.deps.gateway.call(ctx.deps.agent_name, "inspect_ticket", {"ticket_id": ticket_id})

    if "check_inventory" in allowed_tools:
        @agent.tool
        async def check_inventory(ctx: RunContext[AgentDeps], sku: str, size: str | None = None) -> dict[str, Any]:
            return await ctx.deps.gateway.call(ctx.deps.agent_name, "check_inventory", {"sku": sku, "size": size})

    if "inspect_financial_obligation" in allowed_tools:
        @agent.tool
        async def inspect_financial_obligation(ctx: RunContext[AgentDeps], ticket_id: int) -> dict[str, Any]:
            return await ctx.deps.gateway.call(ctx.deps.agent_name, "inspect_financial_obligation", {"ticket_id": ticket_id})

    if "get_cash_balance" in allowed_tools:
        @agent.tool
        async def get_cash_balance(ctx: RunContext[AgentDeps], account: str = "checking") -> dict[str, Any]:
            return await ctx.deps.gateway.call(ctx.deps.agent_name, "get_cash_balance", {"account": account})


def build_specialist(name: str) -> Agent[AgentDeps, SpecialistReport]:
    instructions = {
        "Inventory": "You are the Inventory specialist. Verify SKU, size, quantity, location, pricing, and whether a request can be fulfilled. Never invent stock or promise replenishment.",
        "Accounting": "You are the Accounting specialist. Verify invoices, leases, due dates, existing payments, checking cash, and whether a payment request would require human approval. Never execute payment.",
        "Facilities": "You are the Facilities specialist. Verify lease and rent obligations, due dates, landlord evidence, and operational urgency. Do not authorize payment.",
        "Customer Service": "You are the Customer Service specialist. Interpret the requester’s operational need, verify the ticket facts and product context, and recommend a truthful customer-facing next step.",
    }[name]
    allowed_tools = {
        "Inventory": {"inspect_ticket", "check_inventory"},
        "Accounting": {"inspect_ticket", "inspect_financial_obligation", "get_cash_balance"},
        "Facilities": {"inspect_ticket", "inspect_financial_obligation"},
        "Customer Service": {"inspect_ticket", "check_inventory"},
    }[name]
    agent = Agent(model(), output_type=SpecialistReport, deps_type=AgentDeps, instructions=instructions, name=f"{name.lower().replace(' ', '_')}_specialist", retries=1)
    _tool_functions(agent, allowed_tools)
    return agent


def build_boss() -> tuple[Agent[None, BossPlan], Agent[None, BossDecision]]:
    planner = Agent(
        model(),
        output_type=BossPlan,
        instructions=(
            "You are Boss for Campus Customs operations. Based only on the supplied ticket facts, choose the first specialist and any additional specialists needed. "
            "Prioritize evidence gathering, use the smallest sufficient team, and never assume a payment or invent missing records."
        ),
        name="boss_planner",
        retries=1,
    )
    decider = Agent(
        model(),
        output_type=BossDecision,
        instructions=(
            "You are Boss making the final operational decision. Reconcile specialist evidence. A payment recommendation is not payment execution. "
            "Use pending_approval when a legitimate payment needs human authorization; use blocked or needs_information when evidence is insufficient. Never claim an action happened unless the evidence says it did."
        ),
        name="boss_decider",
        retries=1,
    )
    return planner, decider


async def run_specialist(name: str, ticket: dict[str, Any], reports: list[SpecialistReport], gateway: MCPGateway, run_id: str) -> SpecialistReport:
    agent = build_specialist(name)
    deps = AgentDeps(run_id=run_id, ticket_id=ticket["id"], agent_name=name, gateway=gateway)
    evidence: list[dict[str, Any]] = []
    if name in ("Inventory", "Customer Service"):
        evidence.append(await gateway.call(name, "inspect_ticket", {"ticket_id": ticket["id"]}))
        if ticket.get("sku"):
            evidence.append(await gateway.call(name, "check_inventory", {"sku": ticket["sku"], "size": ticket.get("size")}))
    if name in ("Accounting", "Facilities"):
        evidence.append(await gateway.call(name, "inspect_financial_obligation", {"ticket_id": ticket["id"]}))
        evidence.append(await gateway.call(name, "get_cash_balance", {"account": "checking"}))
    if not evidence:
        evidence.append(await gateway.call(name, "inspect_ticket", {"ticket_id": ticket["id"]}))
    prompt = json.dumps({"ticket": ticket, "evidence": evidence, "previous_reports": [r.model_dump() for r in reports]}, default=str)
    record_event(run_id=run_id, ticket_id=ticket["id"], agent=name, event_type="agent_started", details={"role": name})
    result = await agent.run(prompt, deps=deps)
    report = result.output
    record_event(run_id=run_id, ticket_id=ticket["id"], agent=name, event_type="agent_report", details=report.model_dump())
    return report


async def run_ticket(ticket_id: int) -> WorkflowResult:
    run_id = uuid.uuid4().hex
    record_event(run_id=run_id, ticket_id=ticket_id, agent="Boss", event_type="workflow_started", details={"ticket_id": ticket_id})
    try:
        async with MCPGateway(run_id=run_id, ticket_id=ticket_id) as gateway:
            ticket_payload = await gateway.call("Boss", "inspect_ticket", {"ticket_id": ticket_id})
            if not ticket_payload.get("ok"):
                raise RuntimeError(ticket_payload.get("error", {}).get("message", "Ticket lookup failed"))
            ticket = ticket_payload["ticket"]
            planner, decider = build_boss()
            plan_result = await planner.run(json.dumps(ticket, default=str))
            plan = plan_result.output
            record_event(run_id=run_id, ticket_id=ticket_id, agent="Boss", event_type="delegation_plan", details=plan.model_dump())
            names: list[str] = []
            for candidate in [plan.first_specialist, *plan.additional_specialists]:
                if candidate not in names and candidate in SPECIALISTS:
                    names.append(candidate)
            reports: list[SpecialistReport] = []
            for name in names:
                record_event(run_id=run_id, ticket_id=ticket_id, agent="Boss", event_type="delegation", details={"to": name})
                reports.append(await run_specialist(name, ticket, reports, gateway, run_id))
            final_prompt = json.dumps({"ticket": ticket, "plan": plan.model_dump(), "specialist_reports": [r.model_dump() for r in reports]}, default=str)
            decision = (await decider.run(final_prompt)).output
            decision.specialists_used = names
            record_event(run_id=run_id, ticket_id=ticket_id, agent="Boss", event_type="decision", details=decision.model_dump())
            payment_request = None
            if decision.should_prepare_payment:
                payment_reason = decision.payment_reason or "Boss requested review of a verified obligation."
                payment_result = await gateway.call("Boss", "prepare_payment_request", {"ticket_id": ticket_id, "requested_by": "Boss", "reason": payment_reason})
                if payment_result.get("ok"):
                    payment_request = payment_result.get("request")
                    decision.status = "pending_approval"
                    record_event(run_id=run_id, ticket_id=ticket_id, agent="Boss", event_type="payment_request", details={"request": payment_request})
                else:
                    decision.status = "blocked"
                    decision.rationale += " Payment preparation failed: " + str(payment_result.get("error"))
            record_event(run_id=run_id, ticket_id=ticket_id, agent="Boss", event_type="workflow_finished", details={"status": decision.status})
            return WorkflowResult(run_id=run_id, ticket_id=ticket_id, status=decision.status, plan=plan, specialist_reports=reports, decision=decision, payment_request=payment_request)
    except Exception as exc:  # noqa: BLE001 - surfaced as a structured workflow failure
        record_event(run_id=run_id, ticket_id=ticket_id, agent="Boss", event_type="workflow_error", details={"error": str(exc)})
        return WorkflowResult(run_id=run_id, ticket_id=ticket_id, status="blocked", error=str(exc))

