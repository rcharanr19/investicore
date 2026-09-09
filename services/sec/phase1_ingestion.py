from __future__ import annotations

import hashlib
import logging
import threading
from datetime import date, datetime, timezone, timedelta
from typing import Any

from postgrest.types import ReturnMethod

from database.client import get_supabase_client
from services.sec.company import format_cik
from services.sec.financial_interpretation import fiscal_year_duration_status, metric_kind
from services.sec.financial_validation import validate_balance_sheet, validate_cash_flow, validate_share_change
from services.sec.filings import SECFilingService
from services.sec.filings import sec_filing_service
from services.sec.statements import SECStatementReconstructor
from services.sec.submissions import SECSubmissionsService
from services.sec.submissions import sec_submissions_service
from services.sec.xbrl import SECXBRLService
from services.sec.xbrl import SEC_COMPANY_FACTS_URL

logger = logging.getLogger(__name__)

STORAGE_BUCKET = "sec-filings"
ANNUAL_FORMS = {"10-K", "10-K/A"}
QUARTERLY_FORMS = {"10-Q", "10-Q/A"}
EVENT_FORMS = {"8-K", "8-K/A"}
TTM_FLOW_METRICS = {
    "revenue", "gross_profit", "operating_income", "net_income", "operating_cash_flow", "capex", "free_cash_flow", "eps_basic", "eps_diluted",
}
_BACKGROUND_PRIMARY_DOWNLOADS: set[str] = set()
_BACKGROUND_PRIMARY_DOWNLOADS_LOCK = threading.Lock()


def filing_storage_path(cik: int | str, form_type: str, accession_number: str, filename: str) -> str:
    """Return the deterministic, provenance-readable Storage path for an SEC artifact."""
    safe_form = form_type.upper().replace("/", "-")
    safe_accession = accession_number.replace("-", "")
    safe_filename = filename.rsplit("/", maxsplit=1)[-1] or "filing.html"
    return f"{format_cik(cik)}/{safe_form}/{safe_accession}/{safe_filename}"


def calculate_ttm_from_quarterly_records(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Derive TTM only from four complete stored quarterly observations."""
    if len(records) < 4:
        return None
    quarters = sorted(records, key=lambda row: str(row.get("period_end") or ""))[-4:]
    result: dict[str, Any] = {"period_label": f"TTM through {quarters[-1]['period_end']}"}
    metric_names = {name for row in quarters for name in row.get("metrics", {})}
    for name in metric_names:
        values = [row["metrics"].get(name) for row in quarters]
        if name in TTM_FLOW_METRICS:
            result[name] = sum(float(value) for value in values) if all(value is not None for value in values) else None
        else:
            result[name] = quarters[-1]["metrics"].get(name)
    return result


def company_facts_for_filing(
    company_id: str,
    filing_id: str,
    accession_number: str,
    cik: int | str,
    facts: dict[str, Any],
) -> list[dict[str, Any]]:
    """Flatten unchanged SEC Company Facts for one filing into persistence rows."""
    rows: list[dict[str, Any]] = []
    for taxonomy, concepts in facts.get("facts", {}).items():
        for tag, concept in concepts.items():
            for unit, values in concept.get("units", {}).items():
                for fact in values:
                    if fact.get("accn") != accession_number:
                        continue
                    rows.append({
                        "company_id": company_id,
                        "filing_id": filing_id,
                        "accession_number": fact.get("accn"),
                        "taxonomy": taxonomy,
                        "xbrl_tag": tag,
                        "fact_value": fact.get("val"),
                        "unit": unit,
                        "start_date": fact.get("start"),
                        "end_date": fact.get("end"),
                        "instant_date": fact.get("end") if not fact.get("start") else None,
                        "fiscal_year": fact.get("fy"),
                        "fiscal_period": fact.get("fp"),
                        "form_type": fact.get("form"),
                        "filed_date": fact.get("filed"),
                        "frame": fact.get("frame"),
                        "source_url": SEC_COMPANY_FACTS_URL.format(cik=format_cik(cik)),
                    })
    return rows


def all_company_facts(
    company_id: str,
    cik: int | str,
    facts: dict[str, Any],
    filing_ids_by_accession: dict[str, str],
) -> list[dict[str, Any]]:
    """Flatten every available SEC Company Fact; selected filings retain a filing FK."""
    rows: list[dict[str, Any]] = []
    for taxonomy, concepts in facts.get("facts", {}).items():
        for tag, concept in concepts.items():
            for unit, values in concept.get("units", {}).items():
                for fact in values:
                    accession = fact.get("accn")
                    rows.append({
                        "company_id": company_id,
                        "filing_id": filing_ids_by_accession.get(accession),
                        "accession_number": accession,
                        "taxonomy": taxonomy,
                        "xbrl_tag": tag,
                        "fact_value": fact.get("val"),
                        "unit": unit,
                        "start_date": fact.get("start"),
                        "end_date": fact.get("end"),
                        "instant_date": fact.get("end") if not fact.get("start") else None,
                        "fiscal_year": fact.get("fy"),
                        "fiscal_period": fact.get("fp"),
                        "form_type": fact.get("form"),
                        "filed_date": fact.get("filed"),
                        "frame": fact.get("frame"),
                        "source_url": SEC_COMPANY_FACTS_URL.format(cik=format_cik(cik)),
                    })
    return rows


def facts_for_new_accessions(rows: list[dict[str, Any]], known_accessions: set[str]) -> list[dict[str, Any]]:
    """Return raw facts only for SEC filing accessions not already persisted."""
    return [
        row for row in rows
        if row.get("accession_number") and row["accession_number"] not in known_accessions
    ]


def annual_filing_accessions(filings: list[dict[str, Any]]) -> set[str]:
    """Return all distinct annual source accessions available for normalization."""
    return {
        filing["accession_number"]
        for filing in Phase1SECIngestionService._selected_filings(filings)
        if filing.get("form_type", "").upper() in ANNUAL_FORMS
    }


class Phase1SECIngestionService:
    """Storage-backed, accession-idempotent SEC filing refresh for InvestiCore Phase 1."""

    def __init__(
        self,
        submissions: SECSubmissionsService,
        filings: SECFilingService,
        supabase_client: Any | None = None,
        xbrl: SECXBRLService | None = None,
        reconstructor: SECStatementReconstructor | None = None,
    ):
        self.submissions = submissions
        self.filings = filings
        self.client = supabase_client or get_supabase_client()
        self.xbrl = xbrl or SECXBRLService()
        self.reconstructor = reconstructor or SECStatementReconstructor(self.xbrl)

    def _table(self, name: str) -> Any:
        if self.client is None:
            raise RuntimeError("Supabase credentials are required for Phase 1 SEC ingestion.")
        return self.client.schema("investicorev2").table(name)

    def _create_refresh_run(self, company_id: str) -> dict[str, Any]:
        self._table("sec_refresh_runs").update({
            "status": "PARTIAL_FAILURE",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_message": "Refresh was interrupted before a terminal status was recorded.",
        }).eq("company_id", company_id).eq("status", "RUNNING").execute()
        result = self._table("sec_refresh_runs").insert({"company_id": company_id}).execute()
        return result.data[0]

    def _update_refresh_run(self, run_id: str, **data: Any) -> None:
        raw_facts_saved = data.pop("raw_facts_saved", None)
        if raw_facts_saved is not None:
            summary = data.get("summary", {})
            data["summary"] = {**summary, "raw_facts_saved": raw_facts_saved}
        self._table("sec_refresh_runs").update(data).eq("id", run_id).execute()

    def _existing_filings(self, company_id: str) -> dict[str, dict[str, Any]]:
        result = self._table("sec_filings").select("*").eq("company_id", company_id).execute()
        return {record["accession_number"]: record for record in (result.data or [])}

    def _existing_raw_fact_accessions(self, company_id: str) -> set[str]:
        """Read raw-fact accession watermarks in pages to avoid repeat persistence."""
        accessions: set[str] = set()
        offset = 0
        while True:
            rows = (
                self._table("sec_xbrl_facts").select("accession_number")
                .eq("company_id", company_id).range(offset, offset + 999).execute().data
                or []
            )
            accessions.update(row["accession_number"] for row in rows if row.get("accession_number"))
            if len(rows) < 1000:
                return accessions
            offset += 1000

    def financial_history(self, company_id: str, period_type: str) -> list[dict[str, Any]]:
        periods = (
            self._table("financial_periods").select("id,fiscal_year,fiscal_period,period_end,source_filing_id")
            .eq("company_id", company_id).eq("period_type", period_type).order("period_end").execute().data
            or []
        )
        if not periods:
            return []
        period_ids = [period["id"] for period in periods]
        metrics = (
            self._table("financial_metrics").select("financial_period_id,metric_name,metric_value")
            .in_("financial_period_id", period_ids).execute().data
            or []
        )
        metric_map: dict[str, dict[str, Any]] = {period_id: {} for period_id in period_ids}
        for metric in metrics:
            metric_map[metric["financial_period_id"]].setdefault(metric["metric_name"], metric["metric_value"])
        return [{**period, "metrics": metric_map[period["id"]]} for period in periods]

    def current_ttm(self, company_id: str) -> dict[str, Any] | None:
        return calculate_ttm_from_quarterly_records(self.financial_history(company_id, "Quarterly"))

    @staticmethod
    def _selected_filings(filings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Select all annual reporting periods, eight quarters, and 24 months of 8-Ks."""
        annual_by_period: dict[str, dict[str, Any]] = {}
        for filing in filings:
            form = filing.get("form_type", "").upper()
            if form not in ANNUAL_FORMS:
                continue
            report_period = str(filing.get("report_date") or filing.get("filing_date"))
            current = annual_by_period.get(report_period)
            if current is None or (form.endswith("/A") and not current.get("form_type", "").upper().endswith("/A")):
                annual_by_period[report_period] = filing
        annuals = sorted(annual_by_period.values(), key=lambda filing: str(filing.get("filing_date") or ""), reverse=True)
        quarterlies = [f for f in filings if f.get("form_type", "").upper() in QUARTERLY_FORMS][:8]
        cutoff = (date.today() - timedelta(days=731)).isoformat()
        events = [
            f for f in filings
            if f.get("form_type", "").upper() in EVENT_FORMS and str(f.get("filing_date") or "") >= cutoff
        ]
        combined = annuals + quarterlies + events
        return list({filing["accession_number"]: filing for filing in combined}.values())

    def _upsert_filing(self, company_id: str, filing: dict[str, Any]) -> dict[str, Any]:
        form_type = filing["form_type"].upper()
        payload = {
            "company_id": company_id,
            "accession_number": filing["accession_number"],
            "form_type": form_type,
            "filing_date": filing["filing_date"],
            "report_date": filing.get("report_date"),
            "primary_document": filing.get("primary_document"),
            "sec_url": filing["filing_url"],
            "index_url": filing.get("index_url"),
            "filing_items": filing.get("items"),
            "is_xbrl": filing.get("is_xbrl", False),
            "is_inline_xbrl": filing.get("is_inline_xbrl", False),
            "is_amendment": form_type.endswith("/A"),
            "ingestion_status": "DISCOVERED",
        }
        result = self._table("sec_filings").upsert(
            payload, on_conflict="company_id,accession_number"
        ).execute()
        record = result.data[0]
        if record["is_amendment"]:
            original_form = form_type.removesuffix("/A")
            original = (
                self._table("sec_filings").select("id")
                .eq("company_id", company_id).eq("form_type", original_form)
                .eq("report_date", filing.get("report_date")).order("filing_date", desc=True).limit(1).execute().data
                or []
            )
            if original:
                original_id = original[0]["id"]
                self._table("sec_filings").update({"amends_filing_id": original_id, "is_preferred": True}).eq("id", record["id"]).execute()
                self._table("sec_filings").update({"is_preferred": False, "superseded_by_filing_id": record["id"]}).eq("id", original_id).execute()
                record["amends_filing_id"] = original_id
        return record

    def _store_primary_document(self, cik: str, filing: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        existing = (
            self._table("sec_documents")
            .select("*")
            .eq("filing_id", filing["id"])
            .eq("filename", filing["primary_document"])
            .execute()
        )
        if existing.data:
            return existing.data[0], False

        self._table("sec_filings").update({
            "ingestion_status": "DOWNLOADING",
            "last_attempt_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", filing["id"]).execute()

        content, content_hash = self.filings.fetch_filing_document(
            cik, filing["accession_number"], filing["primary_document"]
        )
        if content is None or content_hash is None:
            raise RuntimeError("SEC EDGAR returned no primary-document content.")

        storage_path = filing_storage_path(cik, filing["form_type"], filing["accession_number"], filing["primary_document"])
        self.client.storage.from_(STORAGE_BUCKET).upload(
            storage_path,
            content.encode("utf-8", errors="replace"),
            {"content-type": "text/html", "upsert": "false"},
        )
        document = {
            "filing_id": filing["id"],
            "document_type": "PRIMARY",
            "filename": filing["primary_document"],
            "source_url": filing["sec_url"],
            "storage_bucket": STORAGE_BUCKET,
            "storage_path": storage_path,
            "content_type": "text/html",
            "byte_size": len(content.encode("utf-8", errors="replace")),
            "content_hash": content_hash,
            "is_primary": True,
        }
        result = self._table("sec_documents").insert(document).execute()
        self._table("sec_filings").update({
            "ingestion_status": "DOWNLOADED",
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", filing["id"]).execute()
        return result.data[0], True

    def _store_filing_artifacts(self, cik: str, filing: dict[str, Any]) -> int:
        """Archive SEC-indexed exhibits and XBRL files without duplicating Storage objects or metadata."""
        stored = 0
        for artifact in self.filings.get_filing_artifacts(cik, filing["accession_number"]):
            if artifact["filename"] == filing.get("primary_document"):
                continue
            existing = self._table("sec_documents").select("id").eq("filing_id", filing["id"]).eq("filename", artifact["filename"]).execute().data
            if existing:
                continue
            content, artifact_hash = self.filings.fetch_document_url(artifact["source_url"])
            if content is None or artifact_hash is None:
                continue
            storage_path = filing_storage_path(cik, filing["form_type"], filing["accession_number"], artifact["filename"])
            content_type = "application/xml" if artifact["document_type"] == "XBRL" else "text/html"
            self.client.storage.from_(STORAGE_BUCKET).upload(storage_path, content.encode("utf-8", errors="replace"), {"content-type": content_type, "upsert": "true"})
            self._table("sec_documents").upsert({
                "filing_id": filing["id"], "document_type": artifact["document_type"], "filename": artifact["filename"],
                "source_url": artifact["source_url"], "storage_bucket": STORAGE_BUCKET, "storage_path": storage_path,
                "content_type": content_type, "byte_size": len(content.encode("utf-8", errors="replace")),
                "content_hash": artifact_hash,
            }, on_conflict="filing_id,filename").execute()
            stored += 1
        return stored

    def archive_companion_artifacts(self, company_id: str, cik: int | str, limit: int | None = None) -> dict[str, int]:
        """Resume archival of exhibits and XBRL artifacts without reprocessing financial data."""
        filings = self._table("sec_filings").select("*").eq("company_id", company_id).order("filing_date", desc=True).execute().data or []
        archived = failed = 0
        for filing in filings[:limit]:
            try:
                archived += self._store_filing_artifacts(format_cik(cik), filing)
            except Exception:
                failed += 1
                logger.exception("Companion artifact archive failed for %s", filing["accession_number"])
        return {"archived": archived, "failed": failed}

    def archive_primary_documents(self, company_id: str, cik: int | str) -> dict[str, int]:
        """Archive missing primary SEC HTML documents without reprocessing financial data."""
        filings = self._table("sec_filings").select("*").eq("company_id", company_id).order("filing_date", desc=True).execute().data or []
        archived = failed = 0
        for filing in filings:
            if not filing.get("primary_document"):
                continue
            try:
                _, downloaded = self._store_primary_document(format_cik(cik), filing)
                archived += int(downloaded)
                self._table("sec_filings").update({"ingestion_status": "COMPLETED"}).eq("id", filing["id"]).execute()
            except Exception:
                failed += 1
                logger.exception("Primary HTML archive failed for %s", filing["accession_number"])
        return {"archived": archived, "failed": failed}

    @staticmethod
    def start_primary_html_download(company_id: str, cik: int | str) -> bool:
        """Start one daemon worker per company; returns False when one is already active."""
        with _BACKGROUND_PRIMARY_DOWNLOADS_LOCK:
            if company_id in _BACKGROUND_PRIMARY_DOWNLOADS:
                return False
            _BACKGROUND_PRIMARY_DOWNLOADS.add(company_id)

        def run() -> None:
            try:
                service = Phase1SECIngestionService(
                    sec_submissions_service, sec_filing_service, get_supabase_client()
                )
                service.archive_primary_documents(company_id, cik)
            finally:
                with _BACKGROUND_PRIMARY_DOWNLOADS_LOCK:
                    _BACKGROUND_PRIMARY_DOWNLOADS.discard(company_id)

        threading.Thread(target=run, name=f"sec-html-{company_id}", daemon=True).start()
        return True

    def _upsert_period(self, company_id: str, filing: dict[str, Any], period: dict[str, Any]) -> dict[str, Any]:
        period_end = str(period["period_end"])
        payload = {
            "company_id": company_id,
            "period_type": period["period_type"],
            # SEC Company Facts `fy` can describe the filing context of a
            # comparative fact. The actual period end is the canonical fiscal
            # label for normalized annual and quarterly history.
            "fiscal_year": int(period_end[:4]),
            "fiscal_period": period["fiscal_period"],
            "calendar_year": period_end[:4],
            "period_start": period.get("period_start"),
            "period_end": period_end,
            "source_filing_id": filing["id"],
        }
        result = self._table("financial_periods").upsert(
            payload,
            on_conflict="company_id,period_type,fiscal_year,fiscal_period,period_end",
        ).execute()
        return result.data[0]

    def _persist_metrics(
        self,
        company_id: str,
        filing: dict[str, Any],
        document: dict[str, Any] | None,
        facts: dict[str, Any],
    ) -> int:
        """Persist only periods supplied by this filing, retaining the source relation for every value."""
        annuals, quarterlies = self.reconstructor._discover_periods(facts)
        matching_periods = [
            period for period in annuals + quarterlies
            if period.get("accn") == filing["accession_number"]
        ]
        saved = 0
        for period in matching_periods:
            normalized_period = self._upsert_period(company_id, filing, period)
            metrics = self.reconstructor.reconstruct_statements_for_period(facts, period)
            metric_payloads = []
            for metric in metrics.values():
                metric_payloads.append({
                    "company_id": company_id,
                    "financial_period_id": normalized_period["id"],
                    "metric_name": metric["metric_name"],
                    "metric_value": metric.get("value"),
                    "unit": metric.get("unit", "USD"),
                    "source_filing_id": filing["id"],
                    "source_document_id": document["id"] if document else None,
                    "source_accession_number": filing["accession_number"],
                    "xbrl_namespace": "us-gaap" if metric.get("source_type", "XBRL") == "XBRL" else None,
                    "xbrl_tag": metric.get("source_concept"),
                    "source_period_start": metric.get("period_start") or period.get("period_start"),
                    "source_period_end": metric.get("period_end") or period["period_end"],
                    "source_type": metric.get("source_type", "XBRL"),
                    "confidence": metric.get("confidence", "HIGH"),
                    "metric_kind": metric_kind(metric["metric_name"]),
                    "is_derived": metric.get("is_derived", False),
                    "calculation_formula": metric.get("calculation_formula"),
                    "calculation_method": metric.get("calculation_formula"),
                    "calculation_version": "1" if metric.get("is_derived") else None,
                    "calculated_at": datetime.now(timezone.utc).isoformat() if metric.get("is_derived") else None,
                    "source_periods": [fact.get("end") for fact in metric.get("source_facts", [])],
                    "source_fact_ids": [fact.get("accn") for fact in metric.get("source_facts", [])],
                })
            if metric_payloads:
                self._table("financial_metrics").upsert(
                    metric_payloads,
                    on_conflict="financial_period_id,metric_name,source_filing_id,xbrl_namespace,xbrl_tag",
                ).execute()
                saved += len(metric_payloads)
            self._record_balance_sheet_validation(company_id, filing["id"], normalized_period["id"], metrics)
            self._record_cash_flow_validation(company_id, filing["id"], normalized_period["id"], metrics)
            self._record_period_validations(company_id, filing["id"], normalized_period, metrics)
            self._record_mapping_reviews(company_id, filing["id"], metrics)
        return saved

    def _persist_raw_facts(
        self,
        company_id: str,
        facts: dict[str, Any],
        cik: str,
        filing_ids_by_accession: dict[str, str],
        known_accessions: set[str],
    ) -> int:
        """Persist all available SEC Company Facts unchanged before normalization."""
        rows = facts_for_new_accessions(
            all_company_facts(company_id, cik, facts, filing_ids_by_accession), known_accessions
        )
        for index in range(0, len(rows), 1000):
            self._table("sec_xbrl_facts").upsert(
                rows[index:index + 1000],
                returning=ReturnMethod.minimal,
                on_conflict="company_id,accession_number,taxonomy,xbrl_tag,unit,start_date,end_date,instant_date,frame",
            ).execute()
        return len(rows)

    def _record_mapping_reviews(self, company_id: str, filing_id: str, metrics: dict[str, dict[str, Any]]) -> None:
        required = {"revenue", "net_income", "operating_cash_flow", "cash", "total_assets", "total_liabilities", "total_equity"}
        for metric_name in sorted(required - metrics.keys()):
            self._table("xbrl_mapping_reviews").upsert({
                "company_id": company_id,
                "filing_id": filing_id,
                "canonical_metric": metric_name,
                "review_type": "MISSING_MAPPING",
                "reason": "No canonical XBRL fact was available for this required metric.",
            }, on_conflict="filing_id,canonical_metric,review_type,selected_tag").execute()

    def _record_balance_sheet_validation(
        self,
        company_id: str,
        filing_id: str,
        period_id: str,
        metrics: dict[str, dict[str, Any]],
    ) -> None:
        assets = metrics.get("total_assets", {}).get("value")
        liabilities = metrics.get("total_liabilities", {}).get("value")
        equity = metrics.get("total_equity", {}).get("value")
        result = validate_balance_sheet(assets, liabilities, equity)
        self._table("financial_validation_issues").insert({
            "company_id": company_id,
            "financial_period_id": period_id,
            "source_filing_id": filing_id,
            "check_name": result["validation_type"],
            "validation_type": result["validation_type"],
            "validation_status": result["validation_status"],
            "severity": "WARNING" if result["validation_status"] == "WARNING" else "INFO",
            "expected_value": result["expected_value"],
            "actual_value": result["actual_value"],
            "difference": result["difference"],
            "tolerance": result["tolerance"],
            "message": result["message"],
            "details": {"assets": assets, "liabilities": liabilities, "equity": equity},
        }).execute()

    def _record_cash_flow_validation(
        self,
        company_id: str,
        filing_id: str,
        period_id: str,
        metrics: dict[str, dict[str, Any]],
    ) -> None:
        result = validate_cash_flow(
            metrics.get("cash_beginning", {}).get("value"),
            metrics.get("operating_cash_flow", {}).get("value"),
            metrics.get("cash_flow_investing", {}).get("value"),
            metrics.get("cash_flow_financing", {}).get("value"),
            metrics.get("cash_ending", {}).get("value"),
            metrics.get("cash_flow_fx_effect", {}).get("value"),
        )
        self._table("financial_validation_issues").insert({
            "company_id": company_id,
            "financial_period_id": period_id,
            "source_filing_id": filing_id,
            "check_name": result["validation_type"],
            "validation_type": result["validation_type"],
            "validation_status": result["validation_status"],
            "severity": "WARNING" if result["validation_status"] == "WARNING" else "INFO",
            "expected_value": result["expected_value"],
            "actual_value": result["actual_value"],
            "difference": result["difference"],
            "tolerance": result["tolerance"],
            "message": result["message"],
        }).execute()

    def _record_period_validations(
        self, company_id: str, filing_id: str, period: dict[str, Any], metrics: dict[str, dict[str, Any]]
    ) -> None:
        start, end = period.get("period_start"), period.get("period_end")
        days = None
        if start and end:
            days = (date.fromisoformat(str(end)) - date.fromisoformat(str(start))).days + 1
        fiscal_status = fiscal_year_duration_status(days) if period["period_type"] == "Annual" else "NOT_APPLICABLE"
        database_status = "PASS" if fiscal_status == "VALID_53_WEEK_YEAR" else fiscal_status
        self._table("financial_validation_issues").insert({
            "company_id": company_id, "financial_period_id": period["id"], "source_filing_id": filing_id,
            "check_name": "fiscal_year_duration", "validation_type": "fiscal_year_duration", "validation_status": database_status,
            "severity": "WARNING" if fiscal_status == "REQUIRES_REVIEW" else "INFO",
            "actual_value": days, "message": f"Fiscal year duration classification: {fiscal_status}.",
            "details": {"fiscal_year_classification": fiscal_status},
        }).execute()
        current_shares = metrics.get("shares_outstanding", {}).get("value")
        previous = (
            self._table("financial_metrics").select("metric_value").eq("company_id", company_id).eq("metric_name", "shares_outstanding")
            .order("created_at", desc=True).limit(2).execute().data
            or []
        )
        prior_shares = previous[1]["metric_value"] if len(previous) > 1 else None
        shares = validate_share_change(prior_shares, current_shares)
        self._table("financial_validation_issues").insert({
            "company_id": company_id, "financial_period_id": period["id"], "source_filing_id": filing_id,
            "check_name": shares["validation_type"], "validation_type": shares["validation_type"],
            "validation_status": shares["validation_status"],
            "severity": "WARNING" if shares["validation_status"] == "REQUIRES_REVIEW" else "INFO",
            "expected_value": shares["expected_value"], "actual_value": shares["actual_value"],
            "difference": shares["difference"], "message": shares["message"],
        }).execute()

    def _normalize_filing(
        self,
        company_id: str,
        filing: dict[str, Any],
        document: dict[str, Any] | None,
        facts: dict[str, Any],
    ) -> int:
        if filing["form_type"] not in ANNUAL_FORMS | QUARTERLY_FORMS:
            return 0
        self._table("sec_filings").update({"ingestion_status": "PARSED"}).eq("id", filing["id"]).execute()
        saved = self._persist_metrics(company_id, filing, document, facts)
        self._table("sec_filings").update({
            "ingestion_status": "VALIDATED",
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", filing["id"]).execute()
        self._table("sec_filings").update({"ingestion_status": "COMPLETED"}).eq("id", filing["id"]).execute()
        return saved

    def _persist_ttm(self, company_id: str) -> int:
        quarters = self.financial_history(company_id, "Quarterly")
        if len(quarters) < 4:
            return 0
        window = quarters[-4:]
        ttm = calculate_ttm_from_quarterly_records(window)
        if not ttm:
            return 0
        latest = window[-1]
        period_payload = {
            "company_id": company_id,
            "period_type": "TTM",
            "fiscal_year": latest["fiscal_year"],
            "fiscal_period": "TTM",
            "calendar_year": str(latest["period_end"])[:4],
            "period_start": window[0].get("period_end"),
            "period_end": latest["period_end"],
            "is_derived": True,
            "calculation_method": "sum_last_four_discrete_quarters",
            "calculation_version": "1",
            "calculated_at": datetime.now(timezone.utc).isoformat(),
            "source_period_ids": [row["id"] for row in window],
            "source_filing_ids": [row["source_filing_id"] for row in window if row.get("source_filing_id")],
        }
        period = self._table("financial_periods").upsert(
            period_payload, on_conflict="company_id,period_type,fiscal_year,fiscal_period,period_end"
        ).execute().data[0]
        saved = 0
        metric_payloads = []
        for name, value in ttm.items():
            if name == "period_label" or value is None:
                continue
            metric_payloads.append({
                "company_id": company_id,
                "financial_period_id": period["id"],
                "metric_name": name,
                "metric_value": value,
                "source_type": "DERIVED",
                "metric_kind": metric_kind(name),
                "is_derived": True,
                "is_preferred": True,
                "calculation_method": "sum_last_four_discrete_quarters",
                "calculation_version": "1",
                "calculated_at": datetime.now(timezone.utc).isoformat(),
                "source_periods": [row["id"] for row in window],
                "xbrl_tag": f"TTM:{name}",
            })
        if metric_payloads:
            self._table("financial_metrics").upsert(
                metric_payloads,
                on_conflict="financial_period_id,metric_name,source_filing_id,xbrl_namespace,xbrl_tag",
            ).execute()
            saved = len(metric_payloads)
        return saved

    def refresh_company_sec_data(
        self,
        company_id: str,
        cik: int | str,
        download_primary_documents: bool = False,
        archive_artifacts: bool = False,
    ) -> dict[str, Any]:
        """Discover, deduplicate, and archive only newly required Phase 1 SEC filings."""
        run = self._create_refresh_run(company_id)
        counts = {"discovered_count": 0, "existing_count": 0, "new_count": 0, "downloaded_count": 0, "raw_facts_saved": 0, "normalized_count": 0, "failed_count": 0}
        try:
            phase1_forms = sorted(ANNUAL_FORMS | QUARTERLY_FORMS | EVENT_FORMS)
            filings = self._selected_filings(
                self.submissions.get_all_filings(cik, form_types=phase1_forms, limit=2000)
            )
            selected_annual_accessions = annual_filing_accessions(filings)
            logger.info(
                "SEC Company Facts annual normalization scope for company %s contains %s available fiscal filings.",
                company_id,
                len(selected_annual_accessions),
            )
            counts["discovered_count"] = len(filings)
            existing = self._existing_filings(company_id)
            facts = self.xbrl.get_company_facts(cik)
            if not facts:
                raise RuntimeError("SEC EDGAR returned no XBRL company facts for this issuer.")
            filing_records: dict[str, dict[str, Any]] = {}
            for discovered in filings:
                accession = discovered["accession_number"]
                filing_records[accession] = existing.get(accession) or self._upsert_filing(company_id, discovered)
            counts["raw_facts_saved"] = self._persist_raw_facts(
                company_id,
                facts,
                format_cik(cik),
                {accession: record["id"] for accession, record in filing_records.items()},
                self._existing_raw_fact_accessions(company_id),
            )
            for discovered in filings:
                accession = discovered["accession_number"]
                filing = filing_records[accession]
                if accession in existing and filing.get("ingestion_status") == "COMPLETED":
                    counts["existing_count"] += 1
                    continue
                counts["new_count"] += 1
                try:
                    document = None
                    downloaded = False
                    if filing["form_type"] in ANNUAL_FORMS | QUARTERLY_FORMS:
                        counts["normalized_count"] += self._normalize_filing(
                            company_id, filing, document, facts
                        )
                    if filing["form_type"] not in ANNUAL_FORMS | QUARTERLY_FORMS:
                        self._table("sec_filings").update({
                            "ingestion_status": "COMPLETED",
                            "processed_at": datetime.now(timezone.utc).isoformat(),
                        }).eq("id", filing["id"]).execute()
                    counts["normalized_count"] += self._persist_ttm(company_id)
                    if archive_artifacts and download_primary_documents:
                        try:
                            self._store_filing_artifacts(format_cik(cik), filing)
                        except Exception:
                            logger.exception("Companion artifact archive failed for %s; the primary filing remains complete.", accession)
                    if downloaded:
                        counts["downloaded_count"] += 1
                except Exception as exc:
                    logger.exception("SEC filing ingestion failed for %s", accession)
                    counts["failed_count"] += 1
                    self._table("sec_filings").update({
                        "ingestion_status": "FAILED", "last_error": str(exc), "last_error_type": type(exc).__name__,
                        "failure_stage": "NORMALIZATION", "retry_count": int(filing.get("retry_count") or 0) + 1,
                        "next_retry_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
                    }).eq("id", filing["id"]).execute()
            status = "COMPLETED" if counts["failed_count"] == 0 else "PARTIAL_FAILURE"
            self._update_refresh_run(run["id"], status=status, completed_at=datetime.now(timezone.utc).isoformat(), **counts)
            return {"run_id": run["id"], "status": status, **counts}
        except Exception as exc:
            logger.exception("SEC refresh failed for company %s", company_id)
            self._update_refresh_run(run["id"], status="FAILED", completed_at=datetime.now(timezone.utc).isoformat(), error_message=str(exc), **counts)
            raise


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()