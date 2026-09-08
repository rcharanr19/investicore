from __future__ import annotations

from typing import Any

# Concept Mapping Dictionary: Canonical InvestiCore Metric -> List of candidate US-GAAP / IFRS concepts (in priority order)
CONCEPT_MAP: dict[str, list[str]] = {
    # --- BALANCE SHEET: ASSETS ---
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "Cash",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "marketable_securities": [
        "MarketableSecuritiesCurrent",
        "AvailableForSaleSecuritiesCurrent",
        "ShortTermInvestments",
        "TradingSecuritiesCurrent",
        "OtherShortTermInvestments",
    ],
    "accounts_receivable": [
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
        "AccountsNotesAndLoansReceivableNetCurrent",
    ],
    "inventory": [
        "InventoryNet",
        "InventoryGross",
        "Inventories",
    ],
    "other_current_assets": [
        "OtherAssetsCurrent",
        "PrepaidExpenseAndOtherAssetsCurrent",
        "PrepaidExpenseCurrent",
    ],
    "total_current_assets": [
        "AssetsCurrent",
    ],
    "ppe": [
        "PropertyPlantAndEquipmentNet",
        "PropertyPlantAndEquipmentGross",
    ],
    "goodwill": [
        "Goodwill",
    ],
    "intangibles": [
        "IntangibleAssetsNetExcludingGoodwill",
        "FiniteLivedIntangibleAssetsNet",
        "IndefiniteLivedIntangibleAssetsExcludingGoodwill",
    ],
    "other_assets": [
        "OtherAssetsNoncurrent",
        "OtherAssets",
    ],
    "total_assets": [
        "Assets",
    ],
    # --- BALANCE SHEET: LIABILITIES ---
    "accounts_payable": [
        "AccountsPayableCurrent",
        "AccountsPayableAndAccruedLiabilitiesCurrent",
    ],
    "short_term_debt": [
        "ShortTermBorrowings",
        "CommercialPaper",
        "LongTermDebtCurrent",
        "DebtCurrent",
    ],
    "current_liabilities": [
        "LiabilitiesCurrent",
    ],
    "long_term_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebtAndCapitalLeaseObligations",
        "LongTermDebt",
    ],
    "lease_liabilities": [
        "OperatingLeaseLiabilityNoncurrent",
        "FinanceLeaseLiabilityNoncurrent",
        "OperatingLeaseLiabilityCurrent",
    ],
    "other_liabilities": [
        "OtherLiabilitiesNoncurrent",
        "OtherLiabilitiesCurrent",
    ],
    "total_liabilities": [
        "Liabilities",
    ],
    # --- BALANCE SHEET: EQUITY ---
    "common_equity": [
        "CommonStockValue",
        "CommonStocksIncludingAdditionalPaidInCapital",
    ],
    "preferred_equity": [
        "PreferredStockValue",
    ],
    "retained_earnings": [
        "RetainedEarningsAccumulatedDeficit",
    ],
    "treasury_stock": [
        "TreasuryStockValue",
    ],
    "total_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    # --- INCOME STATEMENT ---
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "TotalRevenuesAndOtherIncome",
    ],
    "cogs": [
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
    ],
    "gross_profit": [
        "GrossProfit",
    ],
    "operating_expenses": [
        "OperatingExpenses",
        "OperatingCostsAndExpenses",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
    ],
    "interest_expense": [
        "InterestExpense",
        "InterestAndDebtExpense",
    ],
    "pretax_income": [
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    ],
    "income_tax": [
        "IncomeTaxExpenseBenefit",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
    ],
    "eps_basic": [
        "EarningsPerShareBasic",
    ],
    "eps_diluted": [
        "EarningsPerShareDiluted",
    ],
    # --- CASH FLOW STATEMENT ---
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsToAcquireProductiveAssets",
        "PaymentsToAcquireCapitalAssets",
    ],
    "sbc": [
        "ShareBasedCompensation",
        "AllocatedShareBasedCompensationExpense",
    ],
    "depreciation_amortization": [
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
    ],
    # --- SHARES ---
    "shares_outstanding": [
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ],
    "shares_diluted": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
        "WeightedAverageNumberOfSharesOutstandingDiluted",
        "CommonStockSharesOutstanding",
    ],
}


class SECConceptMapper:
    """Normalizes raw XBRL concepts into canonical InvestiCore metrics with confidence tracking."""

    @staticmethod
    def get_canonical_concepts(metric_name: str) -> list[str]:
        return CONCEPT_MAP.get(metric_name, [])

    @classmethod
    def map_metric_from_facts(
        cls,
        facts: dict[str, Any],
        metric_name: str,
        form_filter: list[str] | None = None,
        taxonomy: str = "us-gaap",
    ) -> dict[str, Any] | None:
        """Extract a canonical metric from company facts with confidence scoring and evidence metadata."""
        from services.sec.xbrl import sec_xbrl_service

        concepts = cls.get_canonical_concepts(metric_name)
        if not concepts:
            return None

        # Check in order of preference
        for idx, concept in enumerate(concepts):
            fact_val = sec_xbrl_service.get_latest_fact_value(
                facts,
                [concept],
                form_filter=form_filter,
                taxonomy=taxonomy,
            )
            if fact_val is not None and fact_val.get("val") is not None:
                confidence = "HIGH" if idx == 0 else "MEDIUM"
                return {
                    "metric_name": metric_name,
                    "value": fact_val["val"],
                    "unit": fact_val.get("unit", "USD"),
                    "source_concept": concept,
                    "source_label": fact_val.get("label", concept),
                    "fiscal_year": fact_val.get("fy"),
                    "fiscal_period": fact_val.get("fp"),
                    "form": fact_val.get("form"),
                    "period_end": fact_val.get("end"),
                    "period_start": fact_val.get("start"),
                    "filing_date": fact_val.get("filed"),
                    "accession_number": fact_val.get("accn"),
                    "confidence": confidence,
                    "is_derived": False,
                    "calculation_formula": None,
                }

        return None


# Global singleton instance
sec_concept_mapper = SECConceptMapper()
