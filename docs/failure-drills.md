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