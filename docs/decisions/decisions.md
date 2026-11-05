# Design Decisions

Short notes on why I made the main design choices in this project.

## 1. Use CDC (Debezium) instead of copying tables on a schedule

**Context:** The warehouse needs every change from the bank database (inserts, updates and deletes).

**Decision:** Use Debezium to read the Postgres write-ahead log (WAL) and send each change to Redpanda.

**Why**

- It captures updates and deletes, not only new rows.
- It does not run heavy queries on the bank database.
- Changes arrive within seconds instead of waiting for the next scheduled copy.
- After an outage it continues from its saved offset (tested in Drill 1).

**Trade-offs**

- More services to run (Debezium and Redpanda) than a simple scheduled copy.
- If the connector is down for a long time, Postgres keeps its log files, which can fill the disk.

## 2. Use pg8000 instead of psycopg2

**Context:** The Python scripts (simulator, Bronze loader, reconciliation) need to talk to Postgres.

**Decision:** Use `pg8000`, a pure Python driver.

**Why**

- On my Windows machine, Windows Application Control blocked `psycopg2`.
- `pg8000` installs with pip without any compiled parts, so it works on this machine.

**Trade-offs**

- It is slower than `psycopg2`, but the data in this project is small, so it does not matter.

## 3. Use Redpanda as the Kafka-compatible message broker

**Context:** CDC events need a durable queue between Debezium and the Bronze loader.

**Decision:** Use Redpanda, which speaks the Kafka protocol.

**Why**

- It is Kafka-compatible, so Debezium and the Python Kafka client work with it without changes.
- It runs as a single container, which is lighter on a laptop.
- Events stay in the queue while the loader is not running, so nothing is lost.

**Trade-offs**

- A single broker has no high availability. This is fine for a learning project but not for production.

## 4. Fraud rules run as batch SQL, not in real time

**Context:** The fraud rules (velocity, high value, structuring) need to flag suspicious transactions.

**Decision:** Run the rules as SQL on the Silver table (`streaming/fraud.sql`).

**Why**

- SQL rules are easy to read, test and explain.
- A streaming engine (Flink or Spark Streaming) would add a lot of setup. In the lite plan I removed Spark to finish the project on time.

**Trade-offs**

- Alerts appear only when the SQL is run, so they are not real time.
- For real-time fraud detection, I would move these rules to a streaming engine.