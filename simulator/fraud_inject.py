import random
from datetime import datetime, timedelta
import pg8000.dbapi
from faker import Faker

fake = Faker("en_IN")

conn = pg8000.dbapi.connect(
    host="localhost", port=5432,
    database="core_banking", user="bank", password="bank123",
)
cur = conn.cursor()

cur.execute("SELECT account_id FROM accounts")
account_ids = [r[0] for r in cur.fetchall()]
cur.execute("SELECT merchant_id FROM merchants")
merchant_ids = [r[0] for r in cur.fetchall()]


def insert_txn(account_id, amount, created_at):
    cur.execute(
        """INSERT INTO transactions
           (account_id, merchant_id, txn_type, amount, currency,
            channel, device_id, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           RETURNING transaction_id""",
        (account_id, random.choice(merchant_ids), "PURCHASE", amount, "INR",
         random.choice(["UPI", "CARD", "NETBANKING"]),
         fake.uuid4()[:8], created_at),
    )
    txn_id = cur.fetchone()[0]
    cur.execute(
        """INSERT INTO ledger_entries
           (transaction_id, account_id, entry_type, amount, created_at)
           VALUES (%s, %s, 'DEBIT', %s, %s)""",
        (txn_id, account_id, amount, created_at),
    )


accounts = random.sample(account_ids, 5)
now = datetime.now()

# 1) Velocity: 2 accounts, har ek par 6 transactions 75 second me
for acc in accounts[0:2]:
    for i in range(6):
        insert_txn(acc, round(random.uniform(500, 3000), 2),
                   now - timedelta(seconds=i * 15))

# 2) High value: 2 accounts, ek bada transaction
for acc in accounts[2:4]:
    insert_txn(acc, round(random.uniform(60000, 150000), 2), now)

# 3) Structuring: 1 account, 4 transactions 10000 se thode kam, 10 minute ke gap par
for i in range(4):
    insert_txn(accounts[4], round(random.uniform(9000, 9900), 2),
               now - timedelta(minutes=i * 10))

conn.commit()
cur.close()
conn.close()
print("Fraud scenarios inserted: 2 velocity, 2 high value, 1 structuring")