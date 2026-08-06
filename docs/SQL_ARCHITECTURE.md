# CasinoAI — Free Layered SQL Architecture

**Architecture version:** 3.0  
**Database:** SQLite 3  
**Cost:** Free and local  
**Definition version:** 1.0

## Objective

The warehouse separates source data, cleaning, reusable business logic and dashboard outputs. The Streamlit application no longer depends directly on generated Pandas datasets. SQL performs all persistent transformations and business aggregations; Python orchestrates the scripts and trains the ML models.

```text
Synthetic source generator / future daily files
                      │
                      ▼
              raw_* source tables
                      │
                      ▼
             stg_* standardized views
                      │
                      ▼
      dim_* dimensions + fact_* event facts
                      │
                      ▼
           int_* reusable business logic
                      │
          ┌───────────┴────────────┐
          ▼                        ▼
   mart_* dashboard tables   SQL ML feature query
          │                        │
          │                  Python models
          │                        │
          └───────────┬────────────┘
                      ▼
             Streamlit + Plotly
```

## Layer catalogue

### Raw

The raw layer preserves source-shaped data. No KPI should query it directly.

| Table | Grain | Primary business key |
|---|---|---|
| `raw_players` | One player | `player_id` |
| `raw_games` | One game | `game_id` |
| `raw_sessions` | One casino session | `session_id` |
| `raw_transactions` | One payment transaction | `transaction_id` |
| `raw_sports_bets` | One sportsbook bet | `bet_id` |

Unique indexes protect source identifiers. In production, add ingestion metadata such as `source_file`, `ingested_at`, `batch_id` and a source row hash.

### Staging

The `stg_*` views standardize timestamps, trim text, cast numbers, restrict accepted status values and calculate GGR from wagers and payouts. They do not aggregate data.

- `stg_players`
- `stg_games`
- `stg_sessions`
- `stg_transactions`
- `stg_sports_bets`

### Conformed dimensions

| Table | Primary key | Purpose |
|---|---|---|
| `dim_date` | `date_key` in `YYYYMMDD` format | Calendar attributes shared by all facts |
| `dim_player` | `player_id` | Player, market and acquisition attributes |
| `dim_game` | `game_id` | Game, provider and theoretical RTP |

The MVP stores the current player attributes. A production multi-operator warehouse should implement a type-2 slowly changing player dimension when historical VIP, channel or market attribution is required.

### Facts

| Table | Grain | Primary key | Foreign keys |
|---|---|---|---|
| `fact_casino_session` | One settled casino session | `session_id` | player, game, date |
| `fact_transaction` | One payment attempt | `transaction_id` | player, date |
| `fact_sports_bet` | One settled sportsbook bet | `bet_id` | player, date |

Facts contain additive measures, row-level checks, audit timestamps and indexes on common join/filter keys.

### Intermediate business logic

| View | Reusable definition |
|---|---|
| `int_player_first_deposit` | First-ever approved deposit per player |
| `int_player_first_activity` | First casino or sportsbook activity |
| `int_player_activity_daily` | One row per active player/day across products |
| `int_daily_gaming_revenue` | Casino and sportsbook revenue by date/market |

### Data marts

| Mart | Grain | Main consumers |
|---|---|---|
| `mart_executive_daily` | Date × country | Command Center, Finance |
| `mart_game_performance_daily` | Date × country × game | Casino Intelligence |
| `mart_acquisition_daily` | Date × country × channel | Acquisition |
| `mart_payments_daily` | Date × country × method × transaction type | Payments |
| `mart_player_360` | One model-scored player | Player, CRM, Risk, AI |

Each persisted mart contains `updated_at` and `definition_version`. The app still has compatibility views during migration, but high-volume trends now query the marts.

## SQL execution order

```text
10_staging.sql
20_dimensions.sql
30_facts.sql
40_intermediate.sql
50_marts.sql
Python ML training/scoring
60_ml_marts.sql
```

`data/warehouse.py` controls this order. It records every run in `pipeline_runs`, enables foreign-key validation and stops when a quality test fails.

"Python ML training/scoring" is `ml.pipeline.train_and_score()`, which orchestrates one project per KPI family under `ml/` (`ml/churn`, `ml/ltv`, `ml/revenue_forecast`, `ml/anomaly_detection`, `ml/next_best_action`, sharing feature/model-factory/metric code from `ml/shared`) and writes `model_scores`, `model_metrics_v2`, `forecast_backtest`, `ml_anomalies` and `next_best_actions` before `60_ml_marts.sql` runs.

## Built-in quality controls

- uniqueness of player, session, transaction and sportsbook-bet keys;
- no orphan player or game foreign keys;
- casino GGR equals bets minus payouts;
- sportsbook GGR equals stakes minus payouts;
- theoretical RTP remains between 0 and 1;
- raw-to-fact row counts reconcile;
- ML probabilities remain between 0 and 1;
- one ML score per eligible player;
- SQLite foreign-key and integrity checks;
- idempotent full rebuild test.

## Free local rebuild

From the project directory:

```bash
python -m data.generator
pytest -q
streamlit run app.py
```

The first command rebuilds raw data, every SQL layer, five ML models and the post-ML player mart. No paid service is required.

## Why SQLite is appropriate now

- zero infrastructure and zero license cost;
- enough capacity for the current 151,000 event rows;
- portable single-file demo database;
- supports views, CTEs, window functions, constraints and indexes;
- simple deployment on a laptop or Streamlit Community Cloud.

Move to PostgreSQL only when concurrency, real operator ingestion, tenant isolation, larger volumes or production SLAs justify it. The SQL layer names and grains are intentionally designed to make that migration straightforward.

## Production migration path

1. Replace `raw_*` demo generation with append-only ingestion tables.
2. Add `operator_id`, `currency_code`, `batch_id` and source timestamps to every fact.
3. Move the same layers to free PostgreSQL during development.
4. Introduce dbt Core only when model dependency management becomes materially useful.
5. Add incremental loads and late-arriving-data handling.
6. Add authentication, row-level tenant security, secrets and audit retention.

dbt Cloud, Snowflake and managed Airflow are not required for the local MVP. SQLite, Python, pytest, Git and Streamlit are sufficient and free.
