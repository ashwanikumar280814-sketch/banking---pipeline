# Failure Drills

Each drill breaks one part of the pipeline on purpose, then checks that the data is still correct afterwards.

## Drill 1: CDC connector outage and recovery

**Goal:** Check that no data is lost when the Debezium connector stops and starts again.

**What I did**

1. Counted rows before the drill: `bronze.raw_events` = 3157, `core_banking.transactions` = 1435.
2. Stopped the connector container (`docker stop bank_connect`).
3. Ran the simulator (`simulator/live.py`, 200 events) while the connector was down. Transactions in `core_banking` went from 1435 to 1631 (196 new), but none of them reached Redpanda.
4. Started the connector again (`docker start bank_connect`). Its status was RUNNING (connector and task).
5. Ran `streaming/bronze_loader.py`. It saved 407 events and `bronze.raw_events` became 3564 (3157 + 407).
6. Re-ran Silver (`streaming/silver.sql`), Gold (`dbt run`) and the reconciliation job.

**Result: PASS**

- Silver: 1568 clean rows + 63 quarantined rows = 1631, which equals the core bank count.
- Gold: `fact_transactions` = 1568, `dim_customer` = 117 versions (8 customer updates arrived).
- Reconciliation: 7 of 7 checks passed. Total amount in core (16651898.85) equals Silver + quarantine, to the paisa.

**Why it works**

Debezium remembers how far it has read in the Postgres log (its offset). After a restart it continues from that point, so changes made during the outage are delivered late but not lost. The Bronze loader is idempotent (primary key is topic, partition, offset), so running it again does not create duplicates.

**Limits and trade-offs**

- If the connector stays down for a long time, Postgres keeps its log files on disk and they keep growing. In production this needs monitoring and an alert.
- The simulator also creates duplicate and dirty rows on purpose. These are caught in Silver and kept in the quarantine table, not lost.

## Drill 2: Duplicate and late events

**Goal:** Check that duplicate events and late (out-of-order) events do not corrupt the clean tables.

**What I did**

1. The simulator (`simulator/live.py`) creates duplicate, late and dirty events on purpose.
2. After Silver was rebuilt, I counted duplicates and late events, and looked at sample duplicate rows.
3. I compared total rows with distinct transaction IDs in Gold.

**Evidence**

- `silver.transactions_quarantine`: 38 rows with reason DUPLICATE (27 before Drill 1, plus 11 duplicates created in Drill 1).
- Sample duplicates caught: transaction 1003 (account 148, amount 9071.67), 1017 (account 32, amount 13542.27), 1028 (account 85, amount 8193.33).
- `silver.transactions`: 19 rows flagged `is_late = true`.
- `gold.fact_transactions`: 1568 total rows and 1568 distinct transaction IDs.

**Result: PASS**

No transaction is counted twice in Gold.

**Why it works**

Silver keeps one clean copy of each transaction and moves the repeated copies to the quarantine table with a reason, so nothing is silently deleted. Late events are kept, but marked with `is_late` and the original event time (`source_event_ts`), so analysts can still tell them apart.

**Limits and trade-offs**

- Duplicates are recognised by transaction ID only. If a source system sent two different transactions with the same ID, the second one would be quarantined as a duplicate.
- Late events are only flagged. I did not build special logic to restate old reports when a late event arrives.

## Drill 3: Schema change in the source database

**Goal:** Check that adding a new column to a source table does not break the pipeline.

**What I did**

1. Added a new column to the source table: `ALTER TABLE transactions ADD COLUMN risk_flag text` in `core_banking`.
2. Inserted one new transaction that fills the new column (transaction 1632, amount 777.77, `risk_flag` = REVIEW).
3. Ran the Bronze loader, then rebuilt Silver, ran `dbt run`, and ran the reconciliation job.

**Evidence**

- The connector stayed RUNNING. The Bronze loader saved 1 new event.
- `bronze.raw_events` contains the new field inside the JSON: transaction 1632, amount 777.77, `risk_flag` = REVIEW.
- Silver: 1569 clean rows + 63 quarantined rows = 1632, which equals the core bank count.
- Gold: `dbt run` finished with PASS=5 and ERROR=0, and `fact_transactions` has 1569 rows.
- Reconciliation: 7 of 7 checks passed.

**Result: PASS**

The pipeline did not break when the source table got a new column.

**Why it works**

Debezium reads the change from the Postgres log and sends the whole row as JSON. Bronze stores that JSON as it is, so a new field is simply one more key in the JSON. Silver and Gold select only the columns they know, so an unknown new column is ignored and nothing fails.

**Limits and trade-offs**

- The new column `risk_flag` is stored in Bronze but is not yet used in Silver or Gold. To use it, I would add it to `silver.sql` and the dbt models.
- This drill only covered adding a column. Renaming a column or changing its type could break Silver and would need a separate test.

## Drill 4: Corrupted Gold table and backfill

**Goal:** Check that a damaged Gold table is detected by the reconciliation job and can be rebuilt from Silver.

**What I did**

1. Deleted some rows from the Gold fact table on purpose: `DELETE FROM gold.fact_transactions WHERE transaction_id % 10 = 0`. This removed 159 rows (1569 to 1410).
2. Ran the reconciliation job.
3. Rebuilt Gold from Silver with `dbt run` (backfill).
4. Ran the reconciliation job again.

**Evidence**

- Reconciliation after the damage: 5 of 7 checks passed. Two checks failed:
  - `txn rows: silver = gold.fact_transactions`: expected 1569, actual 1410.
  - `txn amount: silver = gold.fact_transactions`: expected 16106968.20, actual 14332691.12.
- `dbt run` finished with PASS=5 and ERROR=0, and `fact_transactions` had 1569 rows again.
- Reconciliation after the backfill: 7 of 7 checks passed.

**Result: PASS**

The damage was detected by an automatic check, and Gold was fully restored from Silver without touching the source database.

**Why it works**

Gold tables are built only from Silver by dbt, so they can be dropped and rebuilt at any time. The reconciliation job compares Gold with Silver and with the source database, so missing rows show up as failed checks.

**Limits and trade-offs**

- The reconciliation job runs only when I start it. In production it would run on a schedule and send an alert when a check fails.
- The checks compare row counts and total amounts. A change that keeps both numbers the same (for example, two amounts swapped between rows) would not be caught.