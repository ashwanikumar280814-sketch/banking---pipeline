import random
import time
import pg8000.dbapi
from faker import Faker

fake = Faker("en_IN")

conn = pg8000.dbapi.connect(
    host="localhost", port=5432,
    database="core_banking", user="bank", password="bank123",
)
cur = conn.cursor()

NUM_EVENTS = 200      # kitne events chalane hain
SLEEP_SECONDS = 0.5   # har event ke beech wait

cur.execute("SELECT account_id FROM accounts")
account_ids = [r[0] for r in cur.fetchall()]
cur.execute("SELECT merchant_id FROM merchants")
merchant_ids = [r[0] for r in cur.fetchall()]
cur.execute("SELECT customer_id FROM customers")
customer_ids = [r[0] for r in cur.fetchall()]

stats = {"normal": 0, "duplicate": 0, "late": 0, "dirty": 0,
         "customer_update": 0, "account_update": 0}


def insert_txn(account_id, merchant_id, txn_type, amount, currency,
               channel, device_id, created_at):
    cur.execute(
        """INSERT INTO transactions
           (account_id, merchant_id, txn_type, amount, currency,
            channel, device_id, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING transaction_id""",
        (account_id, merchant_id, txn_type, amount, currency,
         channel, device_id, created_at),
    )
    txn_id = cur.fetchone()[0]
    entry_type = "CREDIT" if txn_type == "DEPOSIT" else "DEBIT"
    cur.execute(
        """INSERT INTO ledger_entries
           (transaction_id, account_id, entry_type, amount, created_at)
           VALUES (%s, %s, %s, %s, %s)""",
        (txn_id, account_id, entry_type, amount, created_at),
    )
    return txn_id


def random_txn(created_at=None):
    txn_type = random.choice(["PURCHASE", "PURCHASE", "PURCHASE",
                              "WITHDRAWAL", "DEPOSIT", "TRANSFER"])
    return dict(
        account_id=random.choice(account_ids),
        merchant_id=random.choice(merchant_ids) if txn_type == "PURCHASE" else None,
        txn_type=txn_type,
        amount=round(random.uniform(50, 20000), 2),
        currency="INR",
        channel=random.choice(["UPI", "CARD", "ATM", "NETBANKING"]),
        device_id=fake.uuid4()[:8],
        created_at=created_at or fake.date_time_between(start_date="-5s", end_date="now"),
    )


try:
    for i in range(NUM_EVENTS):
        r = random.random()

        if r < 0.75:                      # normal transaction
            insert_txn(**random_txn())
            stats["normal"] += 1

        elif r < 0.82:                    # duplicate (client retry)
            t = random_txn()
            insert_txn(**t)
            insert_txn(**t)
            stats["duplicate"] += 1

        elif r < 0.88:                    # late-arriving (1 se 3 din purana)
            old = fake.date_time_between(start_date="-3d", end_date="-1d")
            insert_txn(**random_txn(created_at=old))
            stats["late"] += 1

        elif r < 0.92:                    # dirty data
            t = random_txn()
            kind = random.choice(["negative", "bad_currency", "no_device"])
            if kind == "negative":
                t["amount"] = -abs(t["amount"])
            elif kind == "bad_currency":
                t["currency"] = "XXX"
            else:
                t["device_id"] = None
            insert_txn(**t)
            stats["dirty"] += 1

        elif r < 0.97:                    # customer update (SCD2 ke liye)
            cid = random.choice(customer_ids)
            if random.random() < 0.7:
                cur.execute(
                    "UPDATE customers SET address=%s, updated_at=NOW() WHERE customer_id=%s",
                    (fake.address().replace("\n", ", ")[:200], cid),
                )
            else:
                cur.execute(
                    "UPDATE customers SET kyc_status=%s, updated_at=NOW() WHERE customer_id=%s",
                    (random.choice(["VERIFIED", "PENDING", "REJECTED"]), cid),
                )
            stats["customer_update"] += 1

        else:                             # account status change
            aid = random.choice(account_ids)
            cur.execute(
                "UPDATE accounts SET status=%s WHERE account_id=%s",
                (random.choice(["ACTIVE", "ACTIVE", "FROZEN", "DORMANT"]), aid),
            )
            stats["account_update"] += 1

        conn.commit()
        time.sleep(SLEEP_SECONDS)

except KeyboardInterrupt:
    print("Stopped by user")
finally:
    conn.commit()
    cur.close()
    conn.close()
    print("Events done:", stats)