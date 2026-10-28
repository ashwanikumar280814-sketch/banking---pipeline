CREATE SCHEMA IF NOT EXISTS silver;

-- Debezium ke timestamp (number ya text) ko normal timestamp me badalta hai
CREATE OR REPLACE FUNCTION silver.to_ts(j jsonb) RETURNS timestamp AS $$
  SELECT CASE
    WHEN j IS NULL OR jsonb_typeof(j) = 'null' THEN NULL
    WHEN jsonb_typeof(j) = 'number' AND (j #>> '{}')::numeric > 100000000000000
      THEN timestamp '1970-01-01' + ((j #>> '{}')::numeric / 1000000.0) * interval '1 second'
    WHEN jsonb_typeof(j) = 'number'
      THEN timestamp '1970-01-01' + ((j #>> '{}')::numeric / 1000.0) * interval '1 second'
    ELSE (j #>> '{}')::timestamp
  END
$$ LANGUAGE sql IMMUTABLE;

-- Har run par Silver Bronze se dobara banta hai (Bronze kabhi badalta nahi)
DROP TABLE IF EXISTS silver.transactions CASCADE;
DROP TABLE IF EXISTS silver.transactions_quarantine CASCADE;
DROP TABLE IF EXISTS silver.customers_history CASCADE;
DROP TABLE IF EXISTS silver.accounts_history CASCADE;

-- 1) Transactions: raw JSON se columns
CREATE TEMP TABLE txn_stage AS
SELECT
  (payload->'payload'->'after'->>'transaction_id')::int   AS transaction_id,
  (payload->'payload'->'after'->>'account_id')::int       AS account_id,
  (payload->'payload'->'after'->>'merchant_id')::int      AS merchant_id,
  payload->'payload'->'after'->>'txn_type'                AS txn_type,
  (payload->'payload'->'after'->>'amount')::numeric(12,2) AS amount,
  payload->'payload'->'after'->>'currency'                AS currency,
  payload->'payload'->'after'->>'status'                  AS status,
  payload->'payload'->'after'->>'channel'                 AS channel,
  payload->'payload'->'after'->>'device_id'               AS device_id,
  silver.to_ts(payload->'payload'->'after'->'created_at') AS created_at,
  payload->'payload'->>'op'                               AS op,
  to_timestamp(((payload->'payload'->>'ts_ms')::bigint) / 1000.0) AT TIME ZONE 'UTC' AS event_ts,
  kafka_offset
FROM bronze.raw_events
WHERE topic = 'bank.public.transactions'
  AND payload->'payload'->>'op' IN ('r','c','u');

-- Ek transaction_id ka sirf latest version
CREATE TEMP TABLE txn_latest AS
SELECT DISTINCT ON (transaction_id) *
FROM txn_stage
ORDER BY transaction_id, kafka_offset DESC;

-- Duplicate pakadna: baaki sab fields same, sirf transaction_id alag
CREATE TEMP TABLE txn_ranked AS
SELECT *,
  ROW_NUMBER() OVER (
    PARTITION BY account_id, merchant_id, txn_type, amount, currency,
                 channel, device_id, created_at
    ORDER BY transaction_id
  ) AS dup_rank
FROM txn_latest;

-- Validation rules
CREATE TEMP TABLE txn_checked AS
SELECT *,
  CASE
    WHEN amount IS NULL OR amount <= 0                         THEN 'NON_POSITIVE_AMOUNT'
    WHEN currency IS NULL OR currency NOT IN ('INR','USD','EUR','GBP') THEN 'INVALID_CURRENCY'
    WHEN device_id IS NULL                                     THEN 'MISSING_DEVICE_ID'
    WHEN dup_rank > 1                                          THEN 'DUPLICATE'
  END AS reason
FROM txn_ranked;

-- Saaf data
CREATE TABLE silver.transactions AS
SELECT transaction_id, account_id, merchant_id, txn_type, amount, currency,
       status, channel, device_id, created_at,
       (op = 'c' AND event_ts - created_at > interval '1 day') AS is_late,
       event_ts AS source_event_ts
FROM txn_checked
WHERE reason IS NULL;
ALTER TABLE silver.transactions ADD PRIMARY KEY (transaction_id);

-- Galat data: delete nahi, wajah ke saath alag table me
CREATE TABLE silver.transactions_quarantine AS
SELECT transaction_id, account_id, merchant_id, txn_type, amount, currency,
       status, channel, device_id, created_at, reason, now() AS quarantined_at
FROM txn_checked
WHERE reason IS NOT NULL;

-- 2) Customers: saari versions (SCD2 ke liye), PII masked
CREATE TABLE silver.customers_history AS
SELECT
  (payload->'payload'->'after'->>'customer_id')::int AS customer_id,
  left(payload->'payload'->'after'->>'full_name', 1) || '*****' AS full_name_masked,
  left(payload->'payload'->'after'->>'email', 1) || '***@' ||
    split_part(payload->'payload'->'after'->>'email', '@', 2)   AS email_masked,
  md5(lower(payload->'payload'->'after'->>'email'))             AS email_token,
  repeat('*', greatest(length(payload->'payload'->'after'->>'phone') - 4, 0)) ||
    right(payload->'payload'->'after'->>'phone', 4)             AS phone_masked,
  md5(payload->'payload'->'after'->>'address')                  AS address_hash,
  payload->'payload'->'after'->>'kyc_status'                    AS kyc_status,
  silver.to_ts(payload->'payload'->'after'->'created_at')       AS created_at,
  silver.to_ts(payload->'payload'->'after'->'updated_at')       AS updated_at,
  payload->'payload'->>'op'                                     AS op,
  to_timestamp(((payload->'payload'->>'ts_ms')::bigint) / 1000.0) AT TIME ZONE 'UTC' AS event_ts,
  kafka_offset
FROM bronze.raw_events
WHERE topic = 'bank.public.customers'
  AND payload->'payload'->>'op' IN ('r','c','u');

-- 3) Accounts: saari versions
CREATE TABLE silver.accounts_history AS
SELECT
  (payload->'payload'->'after'->>'account_id')::int  AS account_id,
  (payload->'payload'->'after'->>'customer_id')::int AS customer_id,
  payload->'payload'->'after'->>'account_type'       AS account_type,
  payload->'payload'->'after'->>'status'             AS status,
  (payload->'payload'->'after'->>'credit_limit')::numeric(12,2) AS credit_limit,
  silver.to_ts(payload->'payload'->'after'->'opened_at') AS opened_at,
  payload->'payload'->>'op'                          AS op,
  to_timestamp(((payload->'payload'->>'ts_ms')::bigint) / 1000.0) AT TIME ZONE 'UTC' AS event_ts,
  kafka_offset
FROM bronze.raw_events
WHERE topic = 'bank.public.accounts'
  AND payload->'payload'->>'op' IN ('r','c','u');