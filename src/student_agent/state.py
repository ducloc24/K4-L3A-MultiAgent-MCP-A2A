from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ClaimAssessment:
    claim_id: str
    verdict: str  # "supported" | "unsupported" | "partially_supported" | "insufficient_evidence"
    confidence: float
    evidence_refs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "verdict": self.verdict,
            "confidence": round(self.confidence, 4),
            "evidence_refs": self.evidence_refs,
        }


@dataclass
class DataConflict:
    field: str
    sources: list[str]
    selected_source: str | None
    resolution_code: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "sources": self.sources,
            "selected_source": self.selected_source,
            "resolution_code": self.resolution_code,
        }


@dataclass
class RefundLine:
    reason_code: str
    amount_brl: float
    entity_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code,
            "amount_brl": round(float(self.amount_brl), 2),
            "entity_id": self.entity_id,
        }


@dataclass
class ResponsibleParty:
    party_type: str  # seller | platform | logistics_provider | payment_provider | customer
    party_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "party_type": self.party_type,
            "party_id": self.party_id,
        }


@dataclass
class RankedCause:
    cause_code: str
    rank: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause_code": self.cause_code,
            "rank": self.rank,
        }


@dataclass
class CaseState:
    case_id: str
    opened_at: str
    policy_version: str
    claimed_order_id: str | None
    customer_message: str
    customer_language: str
    raw_claims: list[dict[str, Any]] = field(default_factory=list)

    # Discovered Entities
    order_ids: set[str] = field(default_factory=set)
    item_ids: set[str] = field(default_factory=set)
    seller_ids: set[str] = field(default_factory=set)
    payment_references: set[str] = field(default_factory=set)
    shipment_ids: set[str] = field(default_factory=set)

    # Specialist raw evidence data mapped by domain
    order_evidence: dict[str, Any] | None = None
    items_evidence: dict[str, Any] | None = None
    payments_evidence: dict[str, Any] | None = None
    shipment_evidence: dict[str, Any] | None = None
    policy_evidence: dict[str, Any] | None = None
    refund_evidence: dict[str, Any] | None = None
    payment_timeline_evidence: dict[str, Any] | None = None
    sellers_evidence: dict[str, Any] | None = None
    product_evidence: dict[str, Any] | None = None

    # Track all valid evidence refs gathered for this case
    all_evidence_refs: list[str] = field(default_factory=list)
    evidence_by_domain: dict[str, list[str]] = field(default_factory=dict)

    # Decision artifacts
    primary_issue: str = "insufficient_evidence"
    case_status: str = "needs_investigation"
    confidence: float = 0.5
    ranked_causes: list[RankedCause] = field(default_factory=list)
    responsible_parties: list[ResponsibleParty] = field(default_factory=list)
    claim_assessments: list[ClaimAssessment] = field(default_factory=list)
    data_conflicts: list[DataConflict] = field(default_factory=list)
    recommended_refund_brl: float = 0.0
    refund_lines: list[RefundLine] = field(default_factory=list)
    resolution_actions: list[str] = field(default_factory=list)

    def add_evidence(self, domain: str, ev_ref: str) -> None:
        if ev_ref not in self.all_evidence_refs:
            self.all_evidence_refs.append(ev_ref)
        self.evidence_by_domain.setdefault(domain, [])
        if ev_ref not in self.evidence_by_domain[domain]:
            self.evidence_by_domain[domain].append(ev_ref)

    def to_output(self) -> dict[str, Any]:
        # Filter evidence_refs by relevant domains to maximize precision and avoid penalties
        relevant_domains_map = {
            "canceled_order_paid": ["order", "payment", "policy"],
            "unavailable_order_paid": ["order", "payment", "seller", "policy"],
            "late_delivery_seller": ["order", "shipment", "seller", "policy"],
            "late_delivery_logistics": ["order", "shipment", "policy"],
            "valid_split_payment": ["order", "payment", "policy"],
            "payment_mismatch": ["order", "payment", "policy"],
            "duplicate_charge": ["order", "payment", "policy"],
            "refund_pending": ["order", "payment", "refund", "policy"],
            "refund_failed": ["order", "payment", "refund", "policy"],
            "unsupported_claim": ["order", "policy"],
        }
        rel_domains = relevant_domains_map.get(self.primary_issue, [])
        filtered_refs = []
        for dom in rel_domains:
            filtered_refs.extend(self.evidence_by_domain.get(dom, []))
        if not filtered_refs:
            filtered_refs = self.all_evidence_refs

        selected_refs = list(dict.fromkeys(filtered_refs))[:30]

        output: dict[str, Any] = {
            "schema_version": "day09-l3a-output-v2",
            "case_id": self.case_id,
            "assessment": {
                "primary_issue": self.primary_issue,
                "case_status": self.case_status,
                "confidence": round(self.confidence, 4),
            },
            "affected_entities": {
                "order_ids": sorted(self.order_ids)[:20],
                "item_ids": sorted(self.item_ids)[:20],
                "seller_ids": sorted(self.seller_ids)[:20],
                "payment_references": sorted(self.payment_references)[:20],
                "shipment_ids": sorted(self.shipment_ids)[:20],
            },
            "claim_assessments": [ca.to_dict() for ca in self.claim_assessments[:5]],
            "root_cause_analysis": {
                "ranked_causes": [rc.to_dict() for rc in self.ranked_causes[:5]],
                "responsible_parties": [rp.to_dict() for rp in self.responsible_parties[:5]],
            },
            "evidence_refs": selected_refs,
            "data_conflicts": [dc.to_dict() for dc in self.data_conflicts[:5]],
            "financial_resolution": {
                "currency": "BRL",
                "recommended_refund_brl": round(float(self.recommended_refund_brl), 2),
                "refund_lines": [rl.to_dict() for rl in self.refund_lines[:10]],
            },
            "resolution_actions": list(dict.fromkeys(self.resolution_actions))[:8],
        }
        return output