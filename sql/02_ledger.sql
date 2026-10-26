CREATE TABLE ledger_entries (
    entry_id       SERIAL PRIMARY KEY,
    transaction_id INT REFERENCES transactions(transaction_id),
    account_id     INT REFERENCES accounts(account_id),
    entry_type     VARCHAR(6) NOT NULL CHECK (entry_type IN ('DEBIT','CREDIT')),
    amount         NUMERIC(12,2) NOT NULL,
    created_at     TIMESTAMP DEFAULT NOW()
);