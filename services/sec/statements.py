from __future__ import annotations

import logging
from typing import Any

from repositories.financial_metric_repository import FinancialMetricRepository
from repositories.financial_period_repository import FinancialPeriodRepository
from repositories.financial_repository import FinancialRepository
from services.ncav import calculate_ncav, calculate_net_cash, calculate_nnwc
from services.sec.financial_interpretation import metric_kind, reconstruct_discrete_quarter
from services.sec.mapper import CONCEPT_MAP, SECConceptMapper
from services.sec.xbrl import SECXBRLService, sec_xbrl_service

logger = logging.getLogger(__name__)


class SECStatementReconstructor:
    """Reconstructs standardized 5-year annual and 8-quarter financial statements

    from SEC EDGAR XBRL company facts with full concept provenance and audit trails.
    """

    def __init__(self, xbrl_service: SECXBRLService | None = None):
        self.xbrl = xbrl_service or sec_xbrl_service

    def _discover_periods(
        self,
        facts: dict[str, Any],
        taxonomy: str = "us-gaap",
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Scans revenue and asset facts to identify valid annual and quarterly fiscal periods."""
        if not facts or "facts" not in facts or taxonomy not in facts["facts"]:
            return [], []

        tax_facts = facts["facts"][taxonomy]

        # Use anchor concepts to discover reported periods
        anchor_concepts = [
            "Revenues",
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "SalesRevenueNet",
            "Assets",
            "AssetsCurrent",
            "NetIncomeLoss",
        ]

        annual_map: dict[int, dict[str, Any]] = {}
        quarterly_map: dict[str, dict[str, Any]] = {}

        for c in anchor_concepts:
            if c in tax_facts:
                units = tax_facts[c].get("units", {})
                for u_list in units.values():
                    for item in u_list:
                        fy = item.get("fy")
                        fp = str(item.get("fp") or "").upper()
                        form = str(item.get("form") or "").upper()
                        end = item.get("end")
                        start = item.get("start")
                        accn = item.get("accn")
                        filed = item.get("filed")

                        if not fy or not end:
                            continue

                        # Annual Period Detection: Form 10-K / 20-F or fp == 'FY'
                        if fp == "FY" or "10-K" in form or "20-F" in form:
                            prev = annual_map.get(fy)
                            should_replace = (
                                not prev
                                or (filed and str(filed) > str(prev.get("filed") or ""))
                                or (
                                    str(filed or "") == str(prev.get("filed") or "")
                                    and str(end) > str(prev.get("period_end") or "")
                                )
                            )
                            if should_replace:
                                annual_map[fy] = {
                                    "period_type": "Annual",
                                    "fiscal_year": int(fy),
                                    "fiscal_period": "FY",
                                    "period_start": start,
                                    "period_end": end,
                                    "form": form,
                                    "filed": filed,
                                    "accn": accn,
                                }
                            # A 10-K supplies the annual value needed to derive Q4.
                            q_key = f"{fy}_Q4"
                            quarterly_map.setdefault(q_key, {
                                "period_type": "Quarterly",
                                "fiscal_year": int(fy),
                                "fiscal_period": "Q4",
                                "fiscal_quarter": 4,
                                "period_start": start,
                                "period_end": end,
                                "form": form,
                                "filed": filed,
                                "accn": accn,
                            })

                        # Quarterly Period Detection: Q1, Q2, Q3, Q4
                        if fp in ("Q1", "Q2", "Q3", "Q4") or "10-Q" in form:
                            q_num = None
                            if fp in ("Q1", "Q2", "Q3", "Q4"):
                                q_num = int(fp[1])
                            elif "Q1" in form:
                                q_num = 1
                            elif "Q2" in form:
                                q_num = 2
                            elif "Q3" in form:
                                q_num = 3
                            elif "Q4" in form:
                                q_num = 4

                            if q_num:
                                q_key = f"{fy}_Q{q_num}"
                                prev_q = quarterly_map.get(q_key)
                                if not prev_q or (filed and str(filed) > str(prev_q.get("filed") or "")):
                                    quarterly_map[q_key] = {
                                        "period_type": "Quarterly",
                                        "fiscal_year": int(fy),
                                        "fiscal_period": f"Q{q_num}",
                                        "fiscal_quarter": q_num,
                                        "period_start": start,
                                        "period_end": end,
                                        "form": form,
                                        "filed": filed,
                                        "accn": accn,
                                    }

        # An annual fact can only yield a Q4 value when the issuer also reported Q3 YTD.
        quarterly_map = {
            key: value for key, value in quarterly_map.items()
            if value["fiscal_period"] != "Q4" or f"{value['fiscal_year']}_Q3" in quarterly_map
        }

        # Sort annual desc by fiscal year
        sorted_annual = sorted(annual_map.values(), key=lambda x: x["fiscal_year"], reverse=True)
        # Sort quarterly desc by period end
        sorted_quarterly = sorted(quarterly_map.values(), key=lambda x: str(x["period_end"]), reverse=True)

        return sorted_annual, sorted_quarterly

    def _extract_metric_for_period(
        self,
        facts: dict[str, Any],
        metric_name: str,
        period: dict[str, Any],
        taxonomy: str = "us-gaap",
    ) -> dict[str, Any] | None:
        """Extracts best matching fact value for a canonical metric within a specific period."""
        if not facts or "facts" not in facts or taxonomy not in facts["facts"]:
            return None

        tax_facts = facts["facts"][taxonomy]
        candidate_concepts = CONCEPT_MAP.get(metric_name, [])
        if not candidate_concepts:
            return None

        p_end = period.get("period_end")
        p_fy = period.get("fiscal_year")
        p_fp = period.get("fiscal_period")
        p_type = period.get("period_type")

        for idx, concept in enumerate(candidate_concepts):
            if concept not in tax_facts:
                continue

            c_data = tax_facts[concept]
            units = c_data.get("units", {})
            label = c_data.get("label", concept)

            if p_type == "Quarterly" and metric_kind(metric_name) == "flow":
                raw_facts = []
                for unit_name, items in units.items():
                    for item in items:
                        if item.get("fy") == p_fy and item.get("val") is not None and item.get("start"):
                            raw_facts.append({**item, "unit": unit_name})
                discrete = reconstruct_discrete_quarter(metric_name, str(p_fp), str(p_end), raw_facts)
                if discrete:
                    primary = discrete["source_facts"][0]
                    return {
                        "metric_name": metric_name,
                        "value": discrete["value"],
                        "unit": primary["unit"],
                        "source_concept": concept,
                        "source_label": label,
                        "source_type": "XBRL" if discrete["method"] == "direct_quarter" else "DERIVED",
                        "confidence": "HIGH" if idx == 0 else "MEDIUM",
                        "accession_number": primary.get("accn"),
                        "filing_date": primary.get("filed"),
                        "form": primary.get("form"),
                        "period_end": p_end,
                        "period_start": primary.get("start"),
                        "is_derived": discrete["method"] != "direct_quarter",
                        "calculation_formula": discrete["method"],
                        "source_facts": discrete["source_facts"],
                    }

            best_match = None
            for u_name, items in units.items():
                for item in items:
                    item_fy = item.get("fy")
                    item_fp = str(item.get("fp") or "").upper()
                    item_end = item.get("end")
                    item_val = item.get("val")

                    if item_val is None:
                        continue

                    # Exact Match conditions
                    is_match = False
                    if p_type == "Annual":
                        # Match FY and end date
                        if item_fy == p_fy and (item_fp == "FY" or item_end == p_end):
                            is_match = True
                    else:  # Quarterly
                        if item_fy == p_fy and (item_fp == p_fp or item_end == p_end):
                            is_match = True

                    if is_match:
                        if not best_match or (item.get("filed") and str(item.get("filed")) > str(best_match.get("filed") or "")):
                            best_match = {
                                "metric_name": metric_name,
                                "value": float(item_val),
                                "unit": u_name,
                                "source_concept": concept,
                                "source_label": label,
                                "source_type": "XBRL",
                                "confidence": "HIGH" if idx == 0 else "MEDIUM",
                                "accession_number": item.get("accn"),
                                "filing_date": item.get("filed"),
                                "form": item.get("form"),
                                "period_end": item_end,
                                "period_start": item.get("start"),
                                "is_derived": False,
                                "calculation_formula": None,
                            }

            if best_match:
                return best_match

        return None

    def reconstruct_statements_for_period(
        self,
        facts: dict[str, Any],
        period: dict[str, Any],
        taxonomy: str = "us-gaap",
    ) -> dict[str, Any]:
        """Reconstructs balance sheet, income statement, cash flow, and shares for a single period."""
        metrics_to_extract = [
            # Balance Sheet
            "cash",
            "marketable_securities",
            "accounts_receivable",
            "inventory",
            "other_current_assets",
            "deferred_revenue",
            "total_current_assets",
            "ppe",
            "goodwill",
            "intangibles",
            "other_assets",
            "total_assets",
            "accounts_payable",
            "short_term_debt",
            "current_liabilities",
            "long_term_debt",
            "lease_liabilities",
            "other_liabilities",
            "deferred_tax_liabilities",
            "deferred_tax_assets",
            "total_liabilities",
            "common_equity",
            "preferred_equity",
            "retained_earnings",
            "treasury_stock",
            "total_equity",
            # Income Statement
            "revenue",
            "cogs",
            "gross_profit",
            "operating_expenses",
            "operating_income",
            "interest_expense",
            "pretax_income",
            "income_tax",
            "net_income",
            "eps_basic",
            "eps_diluted",
            # Cash Flow
            "operating_cash_flow",
            "capex",
            "sbc",
            "depreciation_amortization",
            "cash_flow_investing",
            "cash_flow_financing",
            "cash_beginning",
            "cash_ending",
            "cash_flow_fx_effect",
            # Shares
            "shares_outstanding",
            "shares_diluted",
        ]

        extracted: dict[str, dict[str, Any]] = {}
        for m_name in metrics_to_extract:
            m_res = self._extract_metric_for_period(facts, m_name, period, taxonomy=taxonomy)
            if m_res:
                extracted[m_name] = m_res

        # --- DERIVED / CALCULATED SAFEGUARDS ---
        # 1. Gross Profit derived if missing
        if "gross_profit" not in extracted and "revenue" in extracted and "cogs" in extracted:
            gp_val = extracted["revenue"]["value"] - extracted["cogs"]["value"]
            extracted["gross_profit"] = {
                "metric_name": "gross_profit",
                "value": gp_val,
                "unit": extracted["revenue"].get("unit", "USD"),
                "source_concept": "Derived(revenue - cogs)",
                "source_label": "Derived Gross Profit",
                "source_type": "DERIVED",
                "confidence": "HIGH",
                "accession_number": extracted["revenue"].get("accession_number"),
                "filing_date": extracted["revenue"].get("filing_date"),
                "form": extracted["revenue"].get("form"),
                "period_end": period.get("period_end"),
                "period_start": period.get("period_start"),
                "is_derived": True,
                "calculation_formula": "revenue - cogs",
            }

        # 2. Free Cash Flow
        if "operating_cash_flow" in extracted:
            ocf_val = extracted["operating_cash_flow"]["value"]
            capex_val = extracted["capex"]["value"] if "capex" in extracted else 0.0
            fcf_val = ocf_val - abs(capex_val)
            extracted["free_cash_flow"] = {
                "metric_name": "free_cash_flow",
                "value": fcf_val,
                "unit": extracted["operating_cash_flow"].get("unit", "USD"),
                "source_concept": "Derived(OCF - CapEx)",
                "source_label": "Derived Free Cash Flow",
                "source_type": "DERIVED",
                "confidence": "HIGH",
                "accession_number": extracted["operating_cash_flow"].get("accession_number"),
                "filing_date": extracted["operating_cash_flow"].get("filing_date"),
                "form": extracted["operating_cash_flow"].get("form"),
                "period_end": period.get("period_end"),
                "is_derived": True,
                "calculation_formula": "operating_cash_flow - capex",
            }

        # 3. Total Debt
        st_debt = extracted["short_term_debt"]["value"] if "short_term_debt" in extracted else 0.0
        lt_debt = extracted["long_term_debt"]["value"] if "long_term_debt" in extracted else 0.0
        tot_debt = st_debt + lt_debt
        extracted["total_debt"] = {
            "metric_name": "total_debt",
            "value": tot_debt,
            "unit": "USD",
            "source_concept": "Derived(short_term_debt + long_term_debt)",
            "source_label": "Total Debt",
            "source_type": "DERIVED",
            "confidence": "HIGH",
            "accession_number": None,
            "is_derived": True,
            "calculation_formula": "short_term_debt + long_term_debt",
        }

        # 4. Net Cash
        c_val = extracted["cash"]["value"] if "cash" in extracted else 0.0
        ms_val = extracted["marketable_securities"]["value"] if "marketable_securities" in extracted else 0.0
        extracted["net_cash"] = {
            "metric_name": "net_cash",
            "value": calculate_net_cash(c_val, ms_val, tot_debt),
            "unit": "USD",
            "source_concept": "Derived(cash + securities - debt)",
            "source_label": "Net Cash",
            "source_type": "DERIVED",
            "confidence": "HIGH",
            "is_derived": True,
            "calculation_formula": "cash + marketable_securities - total_debt",
        }

        # 5. NCAV & NNWC
        ca_val = extracted["total_current_assets"]["value"] if "total_current_assets" in extracted else None
        tl_val = extracted["total_liabilities"]["value"] if "total_liabilities" in extracted else None
        ar_val = extracted["accounts_receivable"]["value"] if "accounts_receivable" in extracted else 0.0
        inv_val = extracted["inventory"]["value"] if "inventory" in extracted else 0.0
        oca_val = extracted["other_current_assets"]["value"] if "other_current_assets" in extracted else 0.0

        if ca_val is not None and tl_val is not None:
            extracted["ncav"] = {
                "metric_name": "ncav",
                "value": calculate_ncav(ca_val, tl_val),
                "unit": "USD",
                "source_concept": "Derived(AssetsCurrent - Liabilities)",
                "source_label": "Net Current Asset Value (NCAV)",
                "source_type": "DERIVED",
                "confidence": "HIGH",
                "is_derived": True,
                "calculation_formula": "total_current_assets - total_liabilities",
            }
            extracted["nnwc"] = {
                "metric_name": "nnwc",
                "value": calculate_nnwc(c_val, ms_val, ar_val, inv_val, oca_val, tl_val),
                "unit": "USD",
                "source_concept": "Derived(Cash + 100%Sec + 75%AR + 50%Inv - Liab)",
                "source_label": "Net-Net Working Capital (NNWC)",
                "source_type": "DERIVED",
                "confidence": "HIGH",
                "is_derived": True,
                "calculation_formula": "cash + marketable_securities + (0.75*ar) + (0.50*inv) - total_liabilities",
            }

        return extracted

    def ingest_and_save_full_history(
        self,
        company_id: str,
        cik: int | str,
        period_repository: FinancialPeriodRepository,
        metric_repository: FinancialMetricRepository,
        financial_repository: FinancialRepository | None = None,
        annual_limit: int = 5,
        quarterly_limit: int = 8,
        taxonomy: str = "us-gaap",
    ) -> dict[str, Any]:
        """Full pipeline: Ingests 5 years of annual and 8 quarters of financial statements from SEC XBRL

        into normalized `financial_periods`, `financial_metrics`, and core `financials` repository.
        """
        facts = self.xbrl.get_company_facts(cik)
        if not facts:
            return {"status": "error", "message": f"No XBRL company facts found for CIK {cik}"}

        annual_periods, quarterly_periods = self._discover_periods(facts, taxonomy=taxonomy)
        target_annual = annual_periods[:annual_limit]
        target_quarterly = quarterly_periods[:quarterly_limit]

        saved_periods_count = 0
        saved_metrics_count = 0

        # Process Annual
        for p in target_annual:
            period_rec = period_repository.get_or_create(
                company_id=company_id,
                fiscal_year=p["fiscal_year"],
                period_type="Annual",
                period_end=p["period_end"],
                fiscal_period="FY",
                period_start=p.get("period_start"),
            )
            saved_periods_count += 1
            metrics_dict = self.reconstruct_statements_for_period(facts, p, taxonomy=taxonomy)

            for m_key, m_val in metrics_dict.items():
                metric_payload = {
                    "company_id": company_id,
                    "financial_period_id": period_rec["id"],
                    "metric_name": m_val["metric_name"],
                    "metric_value": m_val["value"],
                    "unit": m_val.get("unit", "USD"),
                    "source_concept": m_val.get("source_concept"),
                    "source_type": m_val.get("source_type", "XBRL"),
                    "confidence": m_val.get("confidence", "HIGH"),
                    "is_derived": m_val.get("is_derived", False),
                    "calculation_formula": m_val.get("calculation_formula"),
                }
                metric_repository.create(metric_payload)
                saved_metrics_count += 1

            # Sync with core FinancialRepository ($M values)
            if financial_repository is not None:
                def _to_m(val_obj: dict | None) -> float:
                    return float(val_obj["value"]) / 1_000_000.0 if val_obj and val_obj.get("value") is not None else 0.0

                financial_repository.create_or_update(
                    company_id=company_id,
                    fiscal_year=p["fiscal_year"],
                    data={
                        "period_type": "Annual",
                        "fiscal_quarter": None,
                        "revenue": _to_m(metrics_dict.get("revenue")),
                        "gross_profit": _to_m(metrics_dict.get("gross_profit")),
                        "operating_income": _to_m(metrics_dict.get("operating_income")),
                        "net_income": _to_m(metrics_dict.get("net_income")),
                        "eps": float(metrics_dict["eps_diluted"]["value"]) if metrics_dict.get("eps_diluted") else 0.0,
                        "operating_cash_flow": _to_m(metrics_dict.get("operating_cash_flow")),
                        "free_cash_flow": _to_m(metrics_dict.get("free_cash_flow")),
                        "capex": _to_m(metrics_dict.get("capex")),
                        "rnd": _to_m(metrics_dict.get("rnd")),
                        "sbc": _to_m(metrics_dict.get("sbc")),
                        "cash": _to_m(metrics_dict.get("cash")),
                        "debt": _to_m(metrics_dict.get("total_debt")),
                        "shares_outstanding": _to_m(metrics_dict.get("shares_diluted")) or 1.0,
                    },
                    period_type="Annual",
                    fiscal_quarter=None,
                )

        # Process Quarterly
        for q in target_quarterly:
            period_rec = period_repository.get_or_create(
                company_id=company_id,
                fiscal_year=q["fiscal_year"],
                period_type="Quarterly",
                period_end=q["period_end"],
                fiscal_period=q["fiscal_period"],
                period_start=q.get("period_start"),
            )
            saved_periods_count += 1
            metrics_dict = self.reconstruct_statements_for_period(facts, q, taxonomy=taxonomy)

            for m_key, m_val in metrics_dict.items():
                metric_payload = {
                    "company_id": company_id,
                    "financial_period_id": period_rec["id"],
                    "metric_name": m_val["metric_name"],
                    "metric_value": m_val["value"],
                    "unit": m_val.get("unit", "USD"),
                    "source_concept": m_val.get("source_concept"),
                    "source_type": m_val.get("source_type", "XBRL"),
                    "confidence": m_val.get("confidence", "HIGH"),
                    "is_derived": m_val.get("is_derived", False),
                    "calculation_formula": m_val.get("calculation_formula"),
                }
                metric_repository.create(metric_payload)
                saved_metrics_count += 1

            if financial_repository is not None:
                def _to_m(val_obj: dict | None) -> float:
                    return float(val_obj["value"]) / 1_000_000.0 if val_obj and val_obj.get("value") is not None else 0.0

                financial_repository.create_or_update(
                    company_id=company_id,
                    fiscal_year=q["fiscal_year"],
                    data={
                        "period_type": "Quarterly",
                        "fiscal_quarter": q.get("fiscal_quarter"),
                        "revenue": _to_m(metrics_dict.get("revenue")),
                        "gross_profit": _to_m(metrics_dict.get("gross_profit")),
                        "operating_income": _to_m(metrics_dict.get("operating_income")),
                        "net_income": _to_m(metrics_dict.get("net_income")),
                        "eps": float(metrics_dict["eps_diluted"]["value"]) if metrics_dict.get("eps_diluted") else 0.0,
                        "operating_cash_flow": _to_m(metrics_dict.get("operating_cash_flow")),
                        "free_cash_flow": _to_m(metrics_dict.get("free_cash_flow")),
                        "capex": _to_m(metrics_dict.get("capex")),
                        "rnd": _to_m(metrics_dict.get("rnd")),
                        "sbc": _to_m(metrics_dict.get("sbc")),
                        "cash": _to_m(metrics_dict.get("cash")),
                        "debt": _to_m(metrics_dict.get("total_debt")),
                        "shares_outstanding": _to_m(metrics_dict.get("shares_diluted")) or 1.0,
                    },
                    period_type="Quarterly",
                    fiscal_quarter=q.get("fiscal_quarter"),
                )

        return {
            "status": "success",
            "annual_periods_count": len(target_annual),
            "quarterly_periods_count": len(target_quarterly),
            "total_metrics_saved": saved_metrics_count,
        }


# Global singleton instance
sec_statement_reconstructor = SECStatementReconstructor()
