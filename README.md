# Banking Transaction Analytics Pipeline

End-to-end data engineering project that captures changes from a core banking
database (Postgres) using CDC, processes them through Bronze/Silver/Gold layers,
detects fraud in near real time, and reconciles the warehouse against the source ledger.

## Planned stack
Postgres, Debezium, Redpanda (Kafka), Python, dbt, Metabase, Docker Compose

## Status
In progress. Source database and schema done.
