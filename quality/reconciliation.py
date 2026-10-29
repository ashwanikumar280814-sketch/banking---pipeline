import sys
import pg8000.native


def connect(db):
    return pg8000.native.Connection(
        user="bank",
        password="bank123",
        host="localhost",
        port=5432,
        database=db,
    )


core = connect("core_banking")
wh = connect("warehouse")


def one(conn, sql):
    return conn.run(sql)[0]


# Numbers: core_banking (source of truth)
core_customers = one(core, "select count(*) from customers")[0]
core_accounts = one(core, "select count(*) from accounts")[0]
core_merchants = one(core, "select count(*) from merchants")[0]
core_txn_rows, core_txn_amt = one(
    core, "select count(*), coalesce(sum(amount), 0) from transactions"
)

# Numbers: warehouse
gold_customers = one(wh, "select count(*) from gold.dim_customer where is_current")[0]
gold_accounts = one(wh, "select count(*) from gold.dim_account")[0]
gold_merchants = one(wh, "select count(*) from gold.dim_merchant")[0]
silver_rows, silver_amt = one(
    wh, "select count(*), coalesce(sum(amount), 0) from silver.transactions"
)
quar_rows, quar_amt = one(
    wh, "select count(*), coalesce(sum(amount), 0) from silver.transactions_quarantine"
)
fact_rows, fact_amt = one(
    wh, "select count(*), coalesce(sum(amount), 0) from gold.fact_transactions"
)

# (check name, expected, actual)
checks = [
    ("customers: core = gold.dim_customer (current)", core_customers, gold_customers),
    ("accounts: core = gold.dim_account", core_accounts, gold_accounts),
    ("merchants: core = gold.dim_merchant", core_merchants, gold_merchants),
    ("txn rows: core = silver + quarantine", core_txn_rows, silver_rows + quar_rows),
    ("txn amount: core = silver + quarantine", core_txn_amt, silver_amt + quar_amt),
    ("txn rows: silver = gold.fact_transactions", silver_rows, fact_rows),
    ("txn amount: silver = gold.fact_transactions", silver_amt, fact_amt),
]

wh.run(
    """
    create table if not exists gold.reconciliation_report (
        run_at     timestamp default now(),
        check_name text,
        expected   text,
        actual     text,
        status     text
    )
    """
)

failed = 0
for name, expected, actual in checks:
    status = "PASS" if expected == actual else "FAIL"
    if status == "FAIL":
        failed += 1
    wh.run(
        "insert into gold.reconciliation_report (check_name, expected, actual, status) "
        "values (:n, :e, :a, :s)",
        n=name, e=str(expected), a=str(actual), s=status,
    )
    print(f"{status}  {name}  (expected={expected}, actual={actual})")

print(f"\n{len(checks) - failed} of {len(checks)} checks passed")
core.close()
wh.close()
sys.exit(1 if failed else 0)