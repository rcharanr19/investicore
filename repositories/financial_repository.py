from __future__ import annotations

from typing import Any

from database.client import get_db_table


class FinancialRepository:
    def __init__(self):
        # Keyed by f"{company_id}_{fiscal_year}_{period_type}_{fiscal_quarter}"
        self._store: dict[str, dict[str, Any]] = {}

    def create_or_update(
        self,
        company_id: str,
        fiscal_year: int,
        data: dict[str, Any],
        period_type: str = "Annual",
        fiscal_quarter: int | None = None,
    ) -> dict[str, Any]:
        p_type = data.get("period_type", period_type) or "Annual"
        f_quarter = data.get("fiscal_quarter", fiscal_quarter)
        if p_type == "Quarterly" and f_quarter is None:
            f_quarter = 1

        period_label = data.get("period_label")
        if not period_label:
            if p_type == "Quarterly":
                period_label = f"{fiscal_year} Q{f_quarter}"
            else:
                period_label = f"FY{fiscal_year}"

        key = f"{company_id}_{fiscal_year}_{p_type}_{f_quarter or 0}"

        db_payload = {
            "company_id": company_id,
            "fiscal_year": int(fiscal_year),
            "period_type": p_type,
            "fiscal_quarter": f_quarter,
            "period_label": period_label,
            "revenue": float(data.get("revenue", 0.0)),
            "gross_profit": float(data.get("gross_profit", 0.0)),
            "operating_income": float(data.get("operating_income", 0.0)),
            "net_income": float(data.get("net_income", 0.0)),
            "eps": float(data.get("eps", 0.0)),
            "operating_cash_flow": float(data.get("operating_cash_flow", 0.0)),
            "free_cash_flow": float(data.get("free_cash_flow", 0.0)),
            "capex": float(data.get("capex", 0.0)),
            "rnd": float(data.get("rnd", 0.0)),
            "sbc": float(data.get("sbc", 0.0)),
            "cash": float(data.get("cash", 0.0)),
            "debt": float(data.get("debt", 0.0)),
            "shares_outstanding": float(data.get("shares_outstanding", 1.0)),
        }

        table = get_db_table("financials")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                res = table.upsert(db_payload).execute()
                if res and res.data:
                    rec = res.data[0]
                    self._store[key] = rec
                    return rec
            except Exception:
                pass

        record = {
            "id": data.get("id") or f"fin-{key}",
            "company_id": company_id,
            "fiscal_year": int(fiscal_year),
            "period_type": p_type,
            "fiscal_quarter": f_quarter,
            "period_label": period_label,
            "revenue": float(data.get("revenue", 0.0)),
            "gross_profit": float(data.get("gross_profit", 0.0)),
            "operating_income": float(data.get("operating_income", 0.0)),
            "net_income": float(data.get("net_income", 0.0)),
            "eps": float(data.get("eps", 0.0)),
            "operating_cash_flow": float(data.get("operating_cash_flow", 0.0)),
            "free_cash_flow": float(data.get("free_cash_flow", 0.0)),
            "capex": float(data.get("capex", 0.0)),
            "rnd": float(data.get("rnd", 0.0)),
            "sbc": float(data.get("sbc", 0.0)),
            "cash": float(data.get("cash", 0.0)),
            "debt": float(data.get("debt", 0.0)),
            "shares_outstanding": float(data.get("shares_outstanding", 1.0)),
            "updated_at": data.get("updated_at", "2026-09-04T00:00:00Z"),
        }

        self._store[key] = record
        return record

    def get_by_company(self, company_id: str, period_type: str | None = None) -> list[dict[str, Any]]:
        table = get_db_table("financials")
        if table is not None and not str(company_id).startswith("company-"):
            try:
                query = table.select("*").eq("company_id", company_id)
                if period_type:
                    query = query.eq("period_type", period_type)
                res = query.order("fiscal_year").execute()
                if res and res.data is not None:
                    for rec in res.data:
                        if not rec.get("period_type"):
                            rec["period_type"] = "Annual"
                        if not rec.get("period_label"):
                            pt = rec.get("period_type", "Annual")
                            fq = rec.get("fiscal_quarter")
                            fy = rec.get("fiscal_year", "")
                            rec["period_label"] = f"{fy} Q{fq}" if pt == "Quarterly" and fq else f"FY{fy}"

                        pt = rec.get("period_type", "Annual")
                        fq = rec.get("fiscal_quarter") or 0
                        k = f"{company_id}_{rec['fiscal_year']}_{pt}_{fq}"
                        self._store[k] = rec
                    return sorted(res.data, key=lambda x: (x.get("fiscal_year", 0), x.get("fiscal_quarter") or 0))
            except Exception:
                pass

        records = [rec for rec in self._store.values() if rec["company_id"] == company_id]
        if period_type:
            records = [rec for rec in records if rec.get("period_type", "Annual") == period_type]
        for rec in records:
            if not rec.get("period_label"):
                pt = rec.get("period_type", "Annual")
                fq = rec.get("fiscal_quarter")
                fy = rec.get("fiscal_year", "")
                rec["period_label"] = f"{fy} Q{fq}" if pt == "Quarterly" and fq else f"FY{fy}"
        return sorted(records, key=lambda x: (x.get("fiscal_year", 0), x.get("fiscal_quarter") or 0))


    def get_latest(self, company_id: str, period_type: str | None = None) -> dict[str, Any] | None:
        records = self.get_by_company(company_id, period_type=period_type)
        return records[-1] if records else None

    def calculate_ttm(self, company_id: str) -> dict[str, Any] | None:
        quarters = self.get_by_company(company_id, period_type="Quarterly")
        if len(quarters) >= 4:
            last_4 = quarters[-4:]
            latest_q = last_4[-1]
            return {
                "company_id": company_id,
                "period_type": "TTM",
                "period_label": f"TTM ({last_4[0]['period_label']} - {latest_q['period_label']})",
                "fiscal_year": latest_q["fiscal_year"],
                "revenue": sum(q.get("revenue", 0.0) for q in last_4),
                "gross_profit": sum(q.get("gross_profit", 0.0) for q in last_4),
                "operating_income": sum(q.get("operating_income", 0.0) for q in last_4),
                "net_income": sum(q.get("net_income", 0.0) for q in last_4),
                "eps": sum(q.get("eps", 0.0) for q in last_4),
                "operating_cash_flow": sum(q.get("operating_cash_flow", 0.0) for q in last_4),
                "free_cash_flow": sum(q.get("free_cash_flow", 0.0) for q in last_4),
                "capex": sum(q.get("capex", 0.0) for q in last_4),
                "rnd": sum(q.get("rnd", 0.0) for q in last_4),
                "sbc": sum(q.get("sbc", 0.0) for q in last_4),
                # Balance sheet items taken from the most recent quarter
                "cash": latest_q.get("cash", 0.0),
                "debt": latest_q.get("debt", 0.0),
                "shares_outstanding": latest_q.get("shares_outstanding", 1.0),
            }


        # Fallback to latest Annual record if fewer than 4 quarters
        annual = self.get_latest(company_id, period_type="Annual")
        if annual:
            res = dict(annual)
            res["period_type"] = "TTM"
            fy_num = annual.get("fiscal_year", "")
            lbl = annual.get("period_label") or f"FY{fy_num}"
            res["period_label"] = f"TTM ({lbl})"
            return res
        return None

    def calculate_historical_cagr(
        self,
        company_id: str,
        metric: str = "revenue",
        period_type: str = "Annual",
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> float | None:
        records = self.get_by_company(company_id, period_type=period_type)
        if start_year is not None:
            records = [r for r in records if r.get("fiscal_year", 0) >= start_year]
        if end_year is not None:
            records = [r for r in records if r.get("fiscal_year", 0) <= end_year]

        if len(records) < 2:
            return None
        first = float(records[0].get(metric, 0.0) or 0.0)
        last = float(records[-1].get(metric, 0.0) or 0.0)

        if period_type == "Quarterly":
            start_q = records[0].get("fiscal_quarter") or 1
            end_q = records[-1].get("fiscal_quarter") or 1
            years = (records[-1]["fiscal_year"] - records[0]["fiscal_year"]) + (end_q - start_q) / 4.0
            if years <= 0:
                years = (len(records) - 1) / 4.0
        else:
            years = float(records[-1]["fiscal_year"] - records[0]["fiscal_year"])
            if years <= 0:
                years = float(len(records) - 1)

        if first <= 0 or last <= 0 or years <= 0:
            return None
        return (((last / first) ** (1.0 / years)) - 1.0) * 100.0




