from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FilingTypeMetadata:
    form_type: str
    category: str
    description: str
    analytical_purpose: str
    key_questions: list[str]
    financial_relevance: str  # HIGH, MEDIUM, LOW, NONE
    catalyst_relevance: str   # HIGH, MEDIUM, LOW, NONE
    management_relevance: str # HIGH, MEDIUM, LOW, NONE
    ownership_relevance: str  # HIGH, MEDIUM, LOW, NONE


FILING_TAXONOMY: dict[str, FilingTypeMetadata] = {
    # --- ANNUAL FINANCIAL BASELINE ---
    "10-K": FilingTypeMetadata(
        form_type="10-K",
        category="annual_financial",
        description="Annual Report with audited financial statements",
        analytical_purpose="Establishes the annual balance-sheet, liabilities, business baseline, and commitments.",
        key_questions=[
            "What does the company own?",
            "What are its total liabilities and off-balance-sheet commitments?",
            "What is the historical 5-year financial condition?",
            "What are the major structural business and litigation risks?",
        ],
        financial_relevance="HIGH",
        catalyst_relevance="MEDIUM",
        management_relevance="MEDIUM",
        ownership_relevance="LOW",
    ),
    "10-K/A": FilingTypeMetadata(
        form_type="10-K/A",
        category="annual_financial",
        description="Amended Annual Report (Restatements / Corrections)",
        analytical_purpose="Signals potential financial restatements, auditor changes, or governance updates.",
        key_questions=["Was there a restatement or accounting error?", "Did balance sheet asset values change?"],
        financial_relevance="HIGH",
        catalyst_relevance="HIGH",
        management_relevance="MEDIUM",
        ownership_relevance="LOW",
    ),
    "20-F": FilingTypeMetadata(
        form_type="20-F",
        category="annual_financial",
        description="Annual Report for Foreign Private Issuers (IFRS / US-GAAP)",
        analytical_purpose="Establishes foreign issuer baseline balance sheet and structural risks.",
        key_questions=["What is foreign company asset protection?", "What are foreign liabilities & tax exposure?"],
        financial_relevance="HIGH",
        catalyst_relevance="MEDIUM",
        management_relevance="MEDIUM",
        ownership_relevance="LOW",
    ),
    # --- QUARTERLY UPDATE & DETECTOR ---
    "10-Q": FilingTypeMetadata(
        form_type="10-Q",
        category="quarterly_financial",
        description="Quarterly Report with unaudited financial statements",
        analytical_purpose="Updates the 10-K baseline to evaluate recent cash burn, working capital, and balance sheet deterioration.",
        key_questions=[
            "What is current financial condition?",
            "Has cash declined or debt increased?",
            "Are receivables or inventory growing faster than sales?",
            "Is the 10-K asset protection thesis still valid?",
        ],
        financial_relevance="HIGH",
        catalyst_relevance="MEDIUM",
        management_relevance="LOW",
        ownership_relevance="LOW",
    ),
    "10-Q/A": FilingTypeMetadata(
        form_type="10-Q/A",
        category="quarterly_financial",
        description="Amended Quarterly Report",
        analytical_purpose="Flags quarterly restatements and working capital adjustments.",
        key_questions=["What quarterly numbers were corrected?"],
        financial_relevance="HIGH",
        catalyst_relevance="MEDIUM",
        management_relevance="LOW",
        ownership_relevance="LOW",
    ),
    "6-K": FilingTypeMetadata(
        form_type="6-K",
        category="quarterly_financial",
        description="Report of Foreign Private Issuer",
        analytical_purpose="Quarterly and material event updates for international filers.",
        key_questions=["What are recent quarterly updates or international corporate actions?"],
        financial_relevance="HIGH",
        catalyst_relevance="HIGH",
        management_relevance="MEDIUM",
        ownership_relevance="LOW",
    ),
    # --- CATALYSTS & MATERIAL EVENTS ---
    "8-K": FilingTypeMetadata(
        form_type="8-K",
        category="material_event",
        description="Current Report for unscheduled material corporate events",
        analytical_purpose="Primary source for value-unlocking catalysts (asset sales, tender offers, restructuring, CEO changes).",
        key_questions=[
            "What materially changed recently?",
            "Is there an active asset monetization or restructuring catalyst?",
            "Did leadership or debt agreements change?",
        ],
        financial_relevance="MEDIUM",
        catalyst_relevance="HIGH",
        management_relevance="HIGH",
        ownership_relevance="MEDIUM",
    ),
    "8-K/A": FilingTypeMetadata(
        form_type="8-K/A",
        category="material_event",
        description="Amended Current Report",
        analytical_purpose="Follow-up details on material agreements, asset sales, or financial transaction terms.",
        key_questions=["What final transaction terms or proceeds were clarified?"],
        financial_relevance="MEDIUM",
        catalyst_relevance="HIGH",
        management_relevance="HIGH",
        ownership_relevance="MEDIUM",
    ),
    # --- MANAGEMENT & INCENTIVE STRUCTURE ---
    "DEF 14A": FilingTypeMetadata(
        form_type="DEF 14A",
        category="management_governance",
        description="Definitive Proxy Statement",
        analytical_purpose="Primary source for executive ownership, compensation structure, ROIC incentives, and entrenchment risk.",
        key_questions=[
            "Who controls the company?",
            "What are management incentives (per-share value creation vs growth for growth's sake)?",
            "Are management and minority shareholders aligned?",
            "Is management entrenched with golden parachutes?",
        ],
        financial_relevance="LOW",
        catalyst_relevance="MEDIUM",
        management_relevance="HIGH",
        ownership_relevance="HIGH",
    ),
    "DEFM14A": FilingTypeMetadata(
        form_type="DEFM14A",
        category="management_governance",
        description="Definitive Proxy Statement Relating to Merger or Acquisition",
        analytical_purpose="Evaluates merger, buyout, or going-private shareholder votes.",
        key_questions=["What are buyout terms and per-share cash consideration?", "Are insiders receiving special payouts?"],
        financial_relevance="HIGH",
        catalyst_relevance="HIGH",
        management_relevance="HIGH",
        ownership_relevance="HIGH",
    ),
    # --- SIGNIFICANT OWNERSHIP & ACTIVIST INVESTORS ---
    "13D": FilingTypeMetadata(
        form_type="13D",
        category="ownership_activist",
        description="Beneficial Ownership Report (>5% with active / activist intent)",
        analytical_purpose="Identifies activist campaigns, board seat demands, asset sale proposals, and takeover interest.",
        key_questions=[
            "Who is the activist investor?",
            "What is their stake and acquisition price?",
            "What are their specific demands (asset monetization, buybacks, board overhaul)?",
        ],
        financial_relevance="MEDIUM",
        catalyst_relevance="HIGH",
        management_relevance="HIGH",
        ownership_relevance="HIGH",
    ),
    "13D/A": FilingTypeMetadata(
        form_type="13D/A",
        category="ownership_activist",
        description="Amended Beneficial Ownership Report (Activist updates)",
        analytical_purpose="Tracks activist stake increases, escalation of demands, or position exits.",
        key_questions=["Did the activist increase ownership or issue a public letter to the board?"],
        financial_relevance="MEDIUM",
        catalyst_relevance="HIGH",
        management_relevance="HIGH",
        ownership_relevance="HIGH",
    ),
    "13G": FilingTypeMetadata(
        form_type="13G",
        category="ownership_activist",
        description="Beneficial Ownership Report (>5% with passive intent)",
        analytical_purpose="Identifies large institutional backing (index funds, mutual funds, long-term value holders).",
        key_questions=["Which institutional managers hold >5%?", "Has passive institutional ownership expanded?"],
        financial_relevance="LOW",
        catalyst_relevance="LOW",
        management_relevance="LOW",
        ownership_relevance="HIGH",
    ),
    "13G/A": FilingTypeMetadata(
        form_type="13G/A",
        category="ownership_activist",
        description="Amended Passive Beneficial Ownership Report",
        analytical_purpose="Tracks institutional ownership accumulation or reduction.",
        key_questions=["Did an institutional holder cross below or above 5%/10%?"],
        financial_relevance="LOW",
        catalyst_relevance="LOW",
        management_relevance="LOW",
        ownership_relevance="HIGH",
    ),
    # --- INSIDER TRANSACTIONS ---
    "4": FilingTypeMetadata(
        form_type="4",
        category="insider_transaction",
        description="Statement of Changes in Beneficial Ownership of Securities",
        analytical_purpose="Tracks discretionary insider buying vs routine selling, grants, and option exercises.",
        key_questions=[
            "Are executives and directors buying with their own capital on the open market?",
            "Is insider buying occurring while stock trades at a deep NCAV discount?",
            "Is insider selling occurring via scheduled 10b5-1 plans or discretionary sales?",
        ],
        financial_relevance="LOW",
        catalyst_relevance="MEDIUM",
        management_relevance="HIGH",
        ownership_relevance="HIGH",
    ),
    "4/A": FilingTypeMetadata(
        form_type="4/A",
        category="insider_transaction",
        description="Amended Insider Transaction Report",
        analytical_purpose="Corrects insider transaction details.",
        key_questions=["What insider trade was adjusted?"],
        financial_relevance="LOW",
        catalyst_relevance="LOW",
        management_relevance="HIGH",
        ownership_relevance="HIGH",
    ),
}


class SECFilingTaxonomyService:
    """Classifies and enriches SEC filings with structured analytical purposes,

    investor questions, and materiality ratings.
    """

    @staticmethod
    def get_metadata(form_type: str) -> FilingTypeMetadata:
        clean = (form_type or "").strip().upper()
        if clean in FILING_TAXONOMY:
            return FILING_TAXONOMY[clean]

        # Handle variations like 424B2, S-1, S-3, etc.
        if clean.startswith("424B") or clean in ("S-1", "S-3", "S-4"):
            return FilingTypeMetadata(
                form_type=clean,
                category="registration_offering",
                description="Securities Offering / Prospectus",
                analytical_purpose="Signals potential share dilution, secondary offerings, or debt issuance.",
                key_questions=["Is the company issuing new shares or warrants?", "How dilutive is the offering?"],
                financial_relevance="MEDIUM",
                catalyst_relevance="HIGH",
                management_relevance="LOW",
                ownership_relevance="MEDIUM",
            )

        # Default fallback
        return FilingTypeMetadata(
            form_type=clean or "OTHER",
            category="other",
            description="Other SEC Filing",
            analytical_purpose="General corporate or regulatory disclosure.",
            key_questions=["What was disclosed in this regulatory submission?"],
            financial_relevance="LOW",
            catalyst_relevance="LOW",
            management_relevance="LOW",
            ownership_relevance="LOW",
        )

    @classmethod
    def classify_filing(cls, filing_dict: dict[str, Any]) -> dict[str, Any]:
        form = filing_dict.get("form_type", "")
        meta = cls.get_metadata(form)
        return {
            **filing_dict,
            "category": meta.category,
            "category_label": meta.category.replace("_", " ").title(),
            "description": meta.description,
            "analytical_purpose": meta.analytical_purpose,
            "key_questions": meta.key_questions,
            "financial_relevance": meta.financial_relevance,
            "catalyst_relevance": meta.catalyst_relevance,
            "management_relevance": meta.management_relevance,
            "ownership_relevance": meta.ownership_relevance,
            "is_amendment": "/A" in form,
        }


# Global singleton instance
sec_taxonomy_service = SECFilingTaxonomyService()
