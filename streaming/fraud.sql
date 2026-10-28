DROP TABLE IF EXISTS silver.fraud_alerts;

CREATE TABLE silver.fraud_alerts AS
WITH t AS (
  SELECT
    transaction_id, account_id, amount, created_at,
    COUNT(*) OVER (
      PARTITION BY account_id ORDER BY created_at
      RANGE BETWEEN INTERVAL '2 minutes' PRECEDING AND CURRENT ROW
    ) AS txns_2min,
    COUNT(*) FILTER (WHERE amount >= 9000 AND amount < 10000) OVER (
      PARTITION BY account_id ORDER BY created_at
      RANGE BETWEEN INTERVAL '1 hour' PRECEDING AND CURRENT ROW
    ) AS near_threshold_1h
  FROM silver.transactions
)
SELECT transaction_id, account_id, amount, created_at,
       'VELOCITY' AS rule, 'HIGH' AS severity,
       txns_2min::text || ' transactions in 2 minutes' AS detail,
       now() AS detected_at
FROM t WHERE txns_2min >= 5
UNION ALL
SELECT transaction_id, account_id, amount, created_at,
       'HIGH_VALUE', 'MEDIUM',
       'amount >= 50000', now()
FROM t WHERE amount >= 50000
UNION ALL
SELECT transaction_id, account_id, amount, created_at,
       'STRUCTURING', 'HIGH',
       near_threshold_1h::text || ' transactions just under 10000 in 1 hour', now()
FROM t WHERE amount >= 9000 AND amount < 10000 AND near_threshold_1h >= 3;