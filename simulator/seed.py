import random
import pg8000.dbapi
from faker import Faker

fake = Faker("en_IN")

conn = pg8000.dbapi.connect(
    host="localhost", port=5432,
    database="core_banking", user="bank", password="bank123",
)
cur = conn.cursor()

NUM_CUSTOMERS = 100
NUM_MERCHANTS = 20
NUM_TRANSACTIONS = 1000

CATEGORIES = ["Grocery", "Fuel", "Restaurant", "Electronics",
              "Travel", "Clothing", "Utilities", "Entertainment"]

# 1. Customers
customer_ids = []
for _ in range(NUM_CUSTOMERS):
    cur.execute(
        """INSERT INTO customers (full_name, email, phone, address, kyc_status)
           VALUES (%s, %s, %s, %s, %s) RETURNING customer_id""",
        (fake.name(), fake.email(), fake.phone_number()[:20],
         fake.address().replace("\n", ", ")[:200],
         random.choice(["VERIFIED", "VERIFIED", "VERIFIED", "PENDING"])),
    )
    customer_ids.append(cur.fetchone()[0])

# 2. Accounts (1 se 2 per customer)
account_ids = []
for cid in customer_ids:
    for _ in range(random.randint(1, 2)):
        acc_type = random.choice(["SAVINGS", "CURRENT", "CREDIT"])
        limit = random.choice([25000, 50000, 100000]) if acc_type == "CREDIT" else 0
        cur.execute(
            """INSERT INTO accounts (customer_id, account_type, credit_limit)
               VALUES (%s, %s, %s) RETURNING account_id""",
            (cid, acc_type, limit),
        )
        account_ids.append(cur.fetchone()[0])

# 3. Merchants
merchant_ids = []
for _ in range(NUM_MERCHANTS):
    cur.execute(
        """INSERT INTO merchants (name, category, country)
           VALUES (%s, %s, %s) RETURNING merchant_id""",
        (fake.company(), random.choice(CATEGORIES), "IN"),
    )
    merchant_ids.append(cur.fetchone()[0])

# 4. Transactions + ledger entries
for _ in range(NUM_TRANSACTIONS):
    txn_type = random.choice(["PURCHASE", "PURCHASE", "PURCHASE",
                              "WITHDRAWAL", "DEPOSIT", "TRANSFER"])
    account_id = random.choice(account_ids)
    merchant_id = random.choice(merchant_ids) if txn_type == "PURCHASE" else None
    amount = round(random.uniform(50, 20000), 2)
    created_at = fake.date_time_between(start_date="-30d", end_date="now")

    cur.execute(
        """INSERT INTO transactions
           (account_id, merchant_id, txn_type, amount, channel, device_id, created_at)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING transaction_id""",
        (account_id, merchant_id, txn_type, amount,
         random.choice(["UPI", "CARD", "ATM", "NETBANKING"]),
         fake.uuid4()[:8], created_at),
    )
    txn_id = cur.fetchone()[0]

    entry_type = "CREDIT" if txn_type == "DEPOSIT" else "DEBIT"
    cur.execute(
        """INSERT INTO ledger_entries
           (transaction_id, account_id, entry_type, amount, created_at)
           VALUES (%s, %s, %s, %s, %s)""",
        (txn_id, account_id, entry_type, amount, created_at),
    )

conn.commit()
cur.close()
conn.close()
print(f"Done: {NUM_CUSTOMERS} customers, {len(account_ids)} accounts, "
      f"{NUM_MERCHANTS} merchants, {NUM_TRANSACTIONS} transactions")