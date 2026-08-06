# Gambit IQ CSV & Excel pilot guide

Data Import Studio accepts UTF-8 CSV files and Excel workbooks (`.xlsx`/`.xls`) up to 50 MB. Comma, semicolon, tab and pipe delimiters are detected automatically for CSV. An Excel workbook can hold one table per named sheet (`players`, `casino_sessions`, ...) — each sheet is treated exactly like its own file — or a single sheet, in which case the filename drives detection instead. Upload related files together so referential checks can be performed before activation.

A `games` sheet/file (`game_id`, name, RTP, provider) is optional: without it, game metadata is derived from whatever is embedded in `casino_sessions`; with it, every session's `game_id` is cross-checked against it before activation.

| Dataset | Required canonical fields | Optional enrichment |
|---|---|---|
| Players | `player_id`, `registration_date`, `country` | channel, device, VIP level, KYC status, age group |
| Casino sessions | `session_id`, `player_id`, `game_id`, `session_start`, total bet, total payout | duration, GGR, bet count, game metadata, RTP, provider |
| Sportsbook bets | `bet_id`, `player_id`, `bet_date`, `sport`, `odds`, `stake`, `payout` | live flag, GGR, event name |
| Transactions | `transaction_id`, `player_id`, `transaction_date`, type, amount, status | payment method, processing fee |
| Bonuses | `bonus_id`, `player_id`, `bonus_date`, type, amount | status, campaign ID |
| Campaigns | `campaign_id`, name, channel, start date | end date, spend, impressions, clicks, conversions |
| KYC/risk events | `event_id`, `player_id`, `event_date`, type, severity | status, risk score, source |

## Controlled workflow

1. Upload one or more files and confirm the detected dataset.
2. Review every suggested column mapping. A source column cannot feed two canonical fields.
3. Run validation and download the quality report when remediation is needed.
4. Resolve all errors. Warnings are visible but do not block activation.
5. Activate the staged warehouse. The prior active warehouse is archived only after the new build succeeds.
6. Review the immutable run summary in import history.

The quality gate checks required columns and values, parseable dates/numbers/booleans, unique primary keys, non-negative monetary and volume fields, RTP/risk ranges, transaction domains, campaign funnel consistency and player/campaign references.

## Honest missing-data behavior

The application calculates only metrics supported by the imported tables. Unavailable model scores and unsupported KPIs are labelled **Missing data**; they are never silently replaced with synthetic estimates. Real ML scoring requires adequate historical depth followed by temporal train, validation and test evaluation.

## Connector roadmap

The same canonical contracts and quality gate will be reused for PostgreSQL/MySQL snapshots, S3 drops and approved APIs. Production stages then add encrypted credentials, tenant isolation, incremental watermarks, daily orchestration, idempotency, lineage, run retention and pipeline alerts.
