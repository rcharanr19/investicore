# Phase 2 Derived Metrics

## Scope

Phase 2 calculates analysis metrics only from preferred Phase 1 normalized financial records and persisted TTM periods. SEC remains the source for accounting values. Yahoo Finance provides only timestamped market-price snapshots for market-based ratios.

Historical annual valuation uses Yahoo Finance's unadjusted `Close` on the SEC fiscal period end, or the immediately preceding trading-day close when the period end is not a trading day. Historical valuation snapshots are stored independently from current prices and only feed their matching annual financial period.

## Period conventions

Annual metrics compare the immediately preceding annual fiscal period. Quarterly growth compares the same fiscal quarter one year earlier. TTM uses the persisted Phase 1 trailing-four-quarter period. A Phase 1 refresh that writes normalized values triggers a Phase 2 recalculation using the latest stored market price, when present.

## Metric groups

- Operating performance: revenue, gross profit, EBIT, EBITDA where depreciation is reported, net income, operating cash flow, and free cash flow.
- Growth and margins: annual or quarterly growth, gross/operating/net/OCF/FCF margins, and explicit 3Y/5Y/10Y annual CAGRs.
- Per share: book value, tangible book value, revenue, free cash flow, net cash, NCAV, and NNWC per diluted share where source inputs exist.
- Profitability: ROE, ROA, ROIC, CFO/net income, and FCF/net income.
- Financial strength: working capital, current and quick ratios, debt/net debt ratios, EBITDA leverage, interest coverage, share dilution, and stock-based compensation ratios.
- Working capital: DSO, DIO, DPO, and cash conversion cycle when comparable balance-sheet and flow inputs are available.
- Valuation: market capitalization, enterprise value, P/S, P/E, P/OCF, P/FCF, P/book, price-to-asset-value ratios, EV multiples, earnings yield, and FCF yield.

## Missing values and provenance

A calculation with missing or economically invalid inputs is saved as `NOT_APPLICABLE`; zero is never substituted for unavailable data. Every derived record stores its formula version, source normalized-period IDs, source metric names, source filing IDs, and market-price snapshot when applicable.

## Research UI

The Financial analysis page presents metric rows across the selected five, ten, or all available fiscal years. It keeps values, optional same-cell year-over-year changes for amounts/per-share/shares, and separate audit lineage. Percentages and multiples do not receive a second year-over-year annotation because they are already ratios.
