# Pocket Option Research Data Workflow

## Scope

Confluence Lab treats Pocket Option connectivity as a **research-data adapter only**. The project does not expose order-placement methods and does not use Martingale or automatic live trading.

Pocket/OTC research must not substitute ordinary EUR/USD history for broker-specific OTC prices. The goal of this workflow is to accumulate Pocket-observed candles plus contemporaneous payout observations while keeping authentication local.

## 1. Keep the session secret local

Set `POCKET_SSID` in your local shell. Do not paste it into source code, GitHub issues, Actions secrets unless you intentionally decide to run a private collector there, or chat messages.

PowerShell:

```powershell
$env:POCKET_SSID="<your-session-value>"
```

macOS/Linux:

```bash
export POCKET_SSID="<your-session-value>"
```

The capture metadata and snapshot manifest deliberately do not persist this value.

## 2. Capture one snapshot

Example:

```bash
confluence-pocket-capture EURUSD_otc \
  --period-seconds 60 \
  --duration-seconds 86400
```

Each capture writes three independent evidence streams:

1. Candle snapshot (`.parquet` by default).
2. Metadata sidecar containing fingerprint and diagnostics.
3. Append-only JSONL records:
   - `data/raw/pocket/snapshot_manifest.jsonl`
   - `data/raw/pocket/payout_observations.jsonl`

The payout observed during a capture is **not backfilled** across the returned historical candles.

## 3. Run a bounded observation session

For useful payout-aware research, use the bounded observer instead of manually repeating captures.

Example six-hour demo-account collection across four OTC pairs:

```bash
confluence-pocket-watch \
  EURUSD_otc GBPUSD_otc USDJPY_otc EURGBP_otc \
  --period-seconds 60 \
  --interval-seconds 60 \
  --duration-hours 6 \
  --snapshot-every 15 \
  --snapshot-duration-seconds 3600
```

That configuration:

- records one current payout observation per asset every 60 seconds;
- captures a recent one-hour candle snapshot every 15 cycles;
- stores every snapshot in the append-only manifest;
- automatically stops after the requested duration;
- uses the demo account unless `--live-account` is explicitly supplied;
- never writes `POCKET_SSID` into the data or metadata.

For a controlled short run, `--iterations N` overrides `--duration-hours`.

The observer rejects polling intervals below 10 seconds. Faster polling is unnecessary for the initial minute-level research design and adds avoidable load.

## 4. Why repeated snapshots are required

A single call can retrieve older candles, but `get_payout()` gives a current payout observation. To perform realistic payout-aware Pocket research, payout must be observed repeatedly through time.

Therefore historical candles and payout history have different provenance:

```text
Pocket historical candle response -> candle snapshot
Pocket current get_payout()       -> timestamped payout observation
```

Do not merge the current payout backward across a day of candles.

## 5. Overlapping captures are expected

Repeated historical requests will often contain many of the same candles. Confluence Lab records every raw snapshot but consolidates research data deterministically:

```bash
confluence-pocket-consolidate \
  --asset EURUSD_otc \
  --period-seconds 60
```

Default behavior:

- identical duplicate timestamps are collapsed;
- if two snapshots disagree on OHLC for the same timestamp, consolidation **fails closed**;
- the output records how many overlapping rows were removed;
- a deterministic dataset fingerprint is written to metadata.

An explicit `--conflict-policy prefer_last` mode exists only for deliberate repair/investigation. Do not use it silently for research evidence.

## 6. Payout alignment rule

The library function `align_payouts_backward()` attaches only the latest payout observation at or before an event timestamp.

It never uses a future observation.

It also enforces a maximum observation age. Example logic for a 120-second tolerance:

```text
trade at 12:01:30
payout observed 12:00:00 -> eligible, age 90s
payout observed 12:02:00 -> future, NEVER eligible
payout observed 11:55:00 -> stale, rejected
```

A trade with no sufficiently recent observed payout must remain payout-unknown rather than receiving a fabricated value.

## 7. Suggested initial capture targets

For research, begin with a small, fixed universe rather than dozens of assets:

```text
EURUSD_otc
GBPUSD_otc
USDJPY_otc
EURGBP_otc
```

Also collect the corresponding regular pairs where Pocket exposes them. This allows later comparison between broker OTC behavior and ordinary market behavior without claiming equivalence.

## 8. Data sufficiency

Do not begin strong strategy claims after one day of capture. The first Pocket-specific research milestone should span multiple weeks and different day/time conditions, with many timestamped payout observations.

Before a Pocket-specific candidate is considered interesting, verify at minimum:

- data fingerprint and snapshot provenance;
- no conflicting candle revisions left unresolved;
- payout coverage around candidate entry timestamps;
- number of eligible resolved trades;
- actual payout-adjusted expectancy;
- ordinary and moving-block bootstrap confidence intervals;
- non-overlap/cooldown stress tests;
- entry-delay sensitivity;
- chronological development/validation/locked-test behavior;
- prospective demo forward testing.

## 9. What the FXCM/Dukascopy results mean

Regular-FX studies are useful for validating the research engine and testing whether a hypothesis has any general market structure behind it. They are **not** Pocket OTC backtests.

Do not label an FXCM or Dukascopy result as Pocket Option performance.

## 10. Security boundary

The expected architecture is:

```text
local POCKET_SSID
      |
      v
PocketResearchAdapter (data only)
      |
      +--> candle snapshots ----> append-only manifest ----> consolidated dataset
      |
      +--> current payout ------> append-only payout observations

No buy/sell API is exposed by Confluence Lab.
```

If the external community Pocket wrapper changes, keep all compatibility changes inside the adapter rather than coupling broker-specific behavior into the backtester or strategy engine.
