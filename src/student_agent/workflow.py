from __future__ import annotations

import asyncio
from typing import Any

from .mcp_gateway import EvidenceGateway
from .special import (
    OrderSpecialist,
    PaymentSpecialist,
    PolicySpecialist,
    ShipmentSpecialist,
    Verifier,
)
from .state import CaseState
from .trace import TraceWriter


async def solve_case(
    case: dict[str, Any], gateway: EvidenceGateway, trace: TraceWriter
) -> dict[str, Any]:
    """Execute the multi-agent coordinator and specialist workflow for one case."""
    case_id = case["case_id"]
    opened_at = case.get("opened_at", "")
    policy_version = case.get("policy_version", "EC_POLICY_V1")
    req = case.get("customer_request", {})
    claimed_order_id = req.get("claimed_order_id")
    customer_message = req.get("message", "")
    customer_language = req.get("language", "vi")
    raw_claims = req.get("claims", [])

    # Initialize Case State
    state = CaseState(
        case_id=case_id,
        opened_at=opened_at,
        policy_version=policy_version,
        claimed_order_id=claimed_order_id,
        customer_message=customer_message,
        customer_language=customer_language,
        raw_claims=raw_claims,
    )

    # Instantiate Specialists
    order_specialist = OrderSpecialist(gateway, trace)
    payment_specialist = PaymentSpecialist(gateway, trace)
    shipment_specialist = ShipmentSpecialist(gateway, trace)
    policy_specialist = PolicySpecialist(gateway, trace)
    verifier = Verifier(trace)

    # 1. Coordinator assigns tasks to domain specialists
    trace.emit(
        case_id=case_id,
        event_type="task_assigned",
        actor="coordinator",
        target="order-agent",
        decision_code="DISPATCH_SPECIALISTS",
    )

    # 2. Domain Specialists gather authoritative MCP evidence concurrently
    await asyncio.gather(
        order_specialist.investigate(state),
        payment_specialist.investigate(state),
        shipment_specialist.investigate(state),
    )

    # 3. Handoff to Policy Agent
    trace.emit(
        case_id=case_id,
        event_type="handoff",
        actor="coordinator",
        target="policy-agent",
        decision_code="ARBITRATE_DISPUTE",
    )

    # 4. Policy Agent arbitration & rule evaluation
    await policy_specialist.evaluate(state)

    # 5. Handoff to Verifier Agent
    trace.emit(
        case_id=case_id,
        event_type="handoff",
        actor="policy-agent",
        target="verifier-agent",
        decision_code="AUDIT_AND_CALIBRATE",
    )

    # 6. Verification & Calibration
    verifier.verify_and_calibrate(state)

    # 7. Convert state to schema-compliant output
    return state.to_output()