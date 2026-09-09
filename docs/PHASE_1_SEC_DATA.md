# InvestiCore Phase 1 SEC Data

## Architecture

`Phase1SECIngestionService.refresh_company_sec_data()` discovers SEC submissions, selects up to 15 annual filings, the latest four quarterly filings, and the prior 24 months of 8-K filings. It compares SEC accession numbers to `investicorev2.sec_filings`, retrieves only new or failed filings, uploads raw artifacts to Supabase Storage, and records metadata in PostgreSQL.

Raw artifacts are private objects in the `sec-filings` bucket. Paths are deterministic:

```text
{cik}/{form_type}/{accession_without_hyphens}/{original_filename}
```

Example:

```text
0001326801/10-K/000132680126000123/meta-20251231.htm
```

## Data model and provenance

`sec_filings` preserves the accession identity, filing/report dates, SEC links, amendment flag, state, retries, and errors. `sec_documents` references Storage paths and hashes. `financial_periods` holds canonical FY, quarterly, and TTM periods. `financial_metrics` records values with source filing/document, accession, XBRL namespace/tag, source period, confidence, and supersession metadata.

## Incremental refresh

The accession number is unique per company. A refresh skips filings already in `DOWNLOADED`, `PARSED`, or `NORMALIZED` state. Failed filings retain their error and retry count and are retried on the next refresh. `sec_refresh_runs` records discovered, existing, new, downloaded, normalized, and failed counts.

## TTM methodology

TTM is a derived view only. It sums the most recent four stored quarterly flow observations and uses the latest quarterly balance-sheet observation. When four quarterly periods are not available, the system returns no TTM; it never labels an annual number as TTM.

## Initial load and later refresh

Initial load: enter a ticker on the SEC data page and select **Refresh SEC data**. The service archives the selected 10-K, 10-Q, and 8-K documents only once.

Later refresh: run the same action after a new 10-Q becomes available. Existing accessions are skipped; only the new accession is downloaded and inserted. The financial normalization stage must then write the new quarterly metrics and recalculate the derived TTM view.

## Current limitations

The refresh persists primary filing documents and normalized XBRL facts. Exhibit discovery/download, cash-flow reconciliation, share-discontinuity review, and automatic amendment-to-original linking are not yet automated. Amended filings are retained independently by accession and their metric provenance is preserved; preferred-value supersession remains a researcher-review workflow.