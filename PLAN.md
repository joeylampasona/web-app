# Phase 0 — Plan

## 1. File tree

```
PLAN.md                               this document
README.md                             operator runbook
requirements.txt                      python deps
config/settings.yaml                  all tunables; data.provider selects the adapter
config/themes.yaml                    curated theme list + ticker membership rules
cli/__init__.py
cli/__main__.py                       universe / rank / scan / catalysts / backtest / publish / demo / all
data/__init__.py
data/types.py                         Bar, TickerRef, EarningsEvent, OptionChain dataclasses
data/ratelimit.py                     token-bucket limiter, 5 calls/min, persisted cursor
data/store.py                         SQLite store + versioned migration runner
data/migrations/001_init.sql          bars, tickers, fundamentals, runs, kv
data/migrations/002_classification.sql industry + theme membership tables
data/adapters/__init__.py             get_adapter(settings) factory
data/adapters/base.py                 DataAdapter ABC
data/adapters/polygon.py              PolygonGroupedAdapter (working implementation)
data/adapters/stooq.py                StooqAdapter (stub, NotImplementedError)
data/adapters/eodhd.py                EODHDAdapter (stub, NotImplementedError)
data/adapters/synthetic.py            SyntheticAdapter — deterministic offline fixtures (see note)
data/edgar.py                         SEC EDGAR companyfacts shares outstanding
data/classify.py                      industry mapping + theme membership
data/universe.py                      the four-stage liquidity funnel
patterns/__init__.py
patterns/indicators.py                sma, atr, true range, 52w high/low, percentiles
patterns/params.py                    typed param objects + JSON schema for all four detectors
patterns/bases.py                     swing/contraction segmentation shared by the detectors
patterns/detectors.py                 vcp, blue_sky, multi_year, ipo_base — pure functions
patterns/flags.py                     squat, failed_poke
patterns/stages.py                    forming / fresh_breakout / climbing / played_out
patterns/scan.py                      run all detectors over the universe, build setups + diff
rankings/__init__.py
rankings/rs.py                        RS composite, 1-99 percentile, "not ranked yet"
rankings/groups.py                    industry + theme aggregation, sector ETF ranking
rankings/breadth.py                   the eight breadth metrics with history series
rankings/rotation.py                  scatter + quadrants at 3 granularities, heating/cooling
rankings/treemap.py                   industry treemap weights
catalysts/__init__.py
catalysts/events.py                   earnings, dividends, splits, index events, readthrough
catalysts/iv.py                       catalyst-expiry IV richness + 5-dot band
backtest/__init__.py
backtest/settings.py                  the settings table from Phase 5, validated
backtest/engine.py                    configurable rule replay
backtest/metrics.py                   result metrics + plain-English summary + provisional flags
publish/__init__.py
publish/writer.py                     writes the out/ tree
publish/schema.py                     meta.json JSON Schema + validator
.github/workflows/nightly.yml         weekdays 18:30 ET
web/…                                 Next.js App Router app (Phase 7, tree listed in web/README.md)
```

## 2. The `DataAdapter` interface

```python
class DataAdapter(abc.ABC):
    name: str

    @abc.abstractmethod
    def get_universe(self) -> list[TickerRef]:
        """Every tradable reference row the provider knows about."""

    @abc.abstractmethod
    def get_grouped_daily(self, date: datetime.date) -> list[Bar]:
        """One call, every US ticker, one session. [] on a non-trading day."""

    @abc.abstractmethod
    def get_reference(self, symbol: str) -> TickerRef | None:
        """Type, exchange, name, industry, list date for one symbol."""

    @abc.abstractmethod
    def get_earnings_dates(self, symbols: Sequence[str]) -> dict[str, list[EarningsEvent]]:
        """Confirmed and estimated earnings dates, screen population only."""

    @abc.abstractmethod
    def get_option_chain(self, symbol: str) -> OptionChain | None:
        """Expiries with per-expiry mean IV. None when no listed options."""
```

## 3. Python dependencies

| Package | Why |
|---|---|
| `requests` | Polygon REST and SEC EDGAR. Already the ecosystem default; no async needed at 5 calls/min. |
| `PyYAML` | `config/settings.yaml` and `config/themes.yaml`. |
| `jsonschema` | Phase 6 verification requires `meta.json` to validate against a schema. |
| `yfinance` | Earnings dates and option chains. The only free source for both. Imported lazily so the core pipeline runs without it. |

Deliberately **not** used: numpy and pandas. Every calculation here is a rolling mean, a true range, a percentile, or a sort over ~3,000 symbols — all of it is fast in pure Python at this size, and dropping the two heaviest wheels makes the nightly Action start in seconds and keeps the install trivial for a non-technical operator. `yfinance` pulls pandas in transitively; that is contained to the catalysts stage.

## 4. Polygon free Basic and grouped daily aggregates

**I cannot confirm this.** I have no Polygon key in this environment and no way to make an authenticated call, and the free tier's endpoint list has moved more than once. Treat it as unverified: sign up, then run

```
curl "https://api.polygon.io/v2/aggs/grouped/locale/us/market/stocks/2026-09-11?adjusted=true&apiKey=YOUR_KEY"
```

A `results` array with several thousand entries means the plan holds. A `NOT_AUTHORIZED` means the whole free-tier premise needs rethinking before anything downstream is worth building — that is a stop condition, not a detail.

## 5. The three things most likely to cause a problem

1. **The grouped endpoint is the single point of failure for the whole free-tier premise.** Everything — universe, RS, detection, backtest — is one call per session against one endpoint. If it is not on free Basic, or its 5 calls/min ceiling makes the ~520-call backfill fragile, there is no cheap fallback that carries the same breadth. Verify it before Phase 1 is approved.
2. **Survivorship bias is not a footnote, it is the backtest's headline.** Free tiers carry no delisted tickers, so every backtest runs on a universe that already survived. Combined with the prior out-of-sample finding that VCP structure had no edge, the honest reading is that any positive result this engine prints is partly an artefact. The `provisional` flag and the published `played_out` bucket are what keep the site credible; they must never be quietly dropped for a cleaner-looking page.
3. **Earnings dates and option chains come from an unofficial, unversioned source.** yfinance scrapes. It breaks without notice, it rate-limits opaquely, and it is the input to both the earnings badge and the entire High IV surface. Those two features need to degrade to "unavailable" cleanly rather than fail the nightly run or, worse, publish stale dates as current.

## Note on the synthetic adapter

`SyntheticAdapter` is not in the original brief. It exists because every verification command in Phases 1-6, and the whole web app, need bars on disk, and no credentials exist in this environment. It generates deterministic pseudo-random bars from a fixed seed, and anything produced from it is stamped `data_source: "synthetic_demo"` in `meta.json`, which the web app renders as a visible banner. Point `data.provider` at `polygon` and the stamp disappears. It is a fixture, not a data source.
