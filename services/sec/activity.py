from __future__ import annotations

import re
import xml.etree.ElementTree as element_tree
from typing import Any

from services.sec.filings import SECFilingService
from services.sec.phase1_ingestion import Phase1SECIngestionService
from services.sec.submissions import SECSubmissionsService


FORM4_TRANSACTION_TYPES = {
    "P": "Open market purchase",
    "S": "Open market sale",
    "M": "Option exercise",
    "A": "Grant or award",
    "F": "Tax withholding",
    "G": "Gift",
}


def _text(node: element_tree.Element, path: str) -> str | None:
    value = node.findtext(path)
    return value.strip() if value else None


def parse_form4_xml(content: str) -> list[dict[str, Any]]:
    """Extract actual non-derivative Form 4 transactions from SEC ownership XML."""
    try:
        root = element_tree.fromstring(content)
    except element_tree.ParseError:
        return []
    if root.tag != "ownershipDocument":
        return []
    owner = _text(root, "reportingOwner/reportingOwnerId/rptOwnerName") or "Unknown reporting person"
    title = _text(root, "reportingOwner/reportingOwnerRelationship/officerTitle")
    rows = []
    for transaction in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = _text(transaction, "transactionCoding/transactionCode") or "OTHER"
        shares = _text(transaction, "transactionAmounts/transactionShares/value")
        price = _text(transaction, "transactionAmounts/transactionPricePerShare/value")
        owned = _text(transaction, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        direct = _text(transaction, "ownershipNature/directOrIndirectOwnership/value")
        shares_number = float(shares) if shares else None
        price_number = float(price) if price else None
        rows.append({
            "reporting_person": owner,
            "officer_title": title,
            "transaction_date": _text(transaction, "transactionDate/value"),
            "transaction_code": code,
            "transaction_type": FORM4_TRANSACTION_TYPES.get(code, "Other transaction"),
            "shares_transacted": shares_number,
            "price_per_share": price_number,
            "total_value": shares_number * price_number if shares_number is not None and price_number is not None else None,
            "shares_owned_after": float(owned) if owned else None,
            "is_direct": direct == "D" if direct else None,
        })
    return rows


def parse_ownership_disclosure(content: str, form_type: str) -> dict[str, Any]:
    """Extract only explicitly disclosed holder, beneficial shares, and percentage from 13D/13G text."""
    plain = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", content))
    percent_match = re.search(r"(?:percent|percentage)\s+of\s+class[^0-9]{0,80}(\d+(?:\.\d+)?)\s*%", plain, re.I)
    shares_match = re.search(r"aggregate\s+amount\s+beneficially\s+owned[^0-9]{0,80}([\d,]+)", plain, re.I)
    holder_match = re.search(r"name\s+of\s+reporting\s+person[^A-Za-z]{0,80}([A-Za-z][A-Za-z .,&'-]{2,80})", plain, re.I)
    return {
        "holder_name": holder_match.group(1).strip() if holder_match else None,
        "shares_beneficially_owned": float(shares_match.group(1).replace(",", "")) if shares_match else None,
        "ownership_pct": float(percent_match.group(1)) if percent_match else None,
        "is_activist": "13D" in form_type.upper(),
    }


class SECActivityService:
    """Persists actual Form 4 transactions and disclosed 13D/13G ownership evidence."""

    def __init__(self, client: Any, submissions: SECSubmissionsService, filings: SECFilingService):
        self.client = client
        self.submissions = submissions
        self.filings = filings
        self.ingestion = Phase1SECIngestionService(submissions, filings, client)

    def ingest(self, company_id: str, cik: str) -> dict[str, int]:
        forms = ["4", "4/A", "13D", "13D/A", "13G", "13G/A"]
        filings = self.submissions.get_all_filings(cik, form_types=forms, limit=500)
        created_insiders = created_ownership = skipped = 0
        for discovered in filings:
            filing = self.ingestion._upsert_filing(company_id, discovered)
            content, _ = self.filings.fetch_filing_document(cik, filing["accession_number"], filing["primary_document"])
            if not content:
                skipped += 1
                continue
            if filing["form_type"] in {"4", "4/A"}:
                transactions = parse_form4_xml(content)
                if not transactions:
                    skipped += 1
                    continue
                for transaction in transactions:
                    self.client.schema("investicorev2").table("insider_transactions").upsert({
                        "company_id": company_id, "filing_id": filing["id"], "source_document_url": filing["sec_url"], **transaction,
                    }, on_conflict="filing_id,transaction_code,transaction_date,shares_transacted,price_per_share").execute()
                    created_insiders += 1
            else:
                disclosure = parse_ownership_disclosure(content, filing["form_type"])
                previous = self.client.schema("investicorev2").table("ownership_disclosures").select("ownership_pct").eq("company_id", company_id).eq("holder_name", disclosure["holder_name"]).order("filing_date", desc=True).limit(1).execute().data or []
                prior_pct = previous[0]["ownership_pct"] if previous else None
                activity = "ACTIVIST_DISCLOSURE" if disclosure["is_activist"] else "OWNERSHIP_DISCLOSURE"
                if disclosure["ownership_pct"] is not None and prior_pct is not None:
                    activity = "OWNERSHIP_INCREASE" if disclosure["ownership_pct"] > float(prior_pct) else "OWNERSHIP_DECREASE" if disclosure["ownership_pct"] < float(prior_pct) else activity
                self.client.schema("investicorev2").table("ownership_disclosures").upsert({
                    "company_id": company_id, "filing_id": filing["id"], "form_type": filing["form_type"], "filing_date": filing["filing_date"],
                    "activity_type": activity, "source_document_url": filing["sec_url"], **disclosure,
                }, on_conflict="filing_id").execute()
                created_ownership += 1
            return {
                "insider_transactions": created_insiders,
                "ownership_disclosures": created_ownership,
                "skipped_filings": skipped,
            }