CREATE TABLE customers (
    customer_id   SERIAL PRIMARY KEY,
    full_name     VARCHAR(100) NOT NULL,
    email         VARCHAR(100),
    phone         VARCHAR(20),
    address       VARCHAR(200),
    kyc_status    VARCHAR(20) DEFAULT 'PENDING',
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW()
);

CREATE TABLE accounts (
    account_id    SERIAL PRIMARY KEY,
    customer_id   INT REFERENCES customers(customer_id),
    account_type  VARCHAR(20) NOT NULL,
    status        VARCHAR(20) DEFAULT 'ACTIVE',
    credit_limit  NUMERIC(12,2) DEFAULT 0,
    opened_at     TIMESTAMP DEFAULT NOW()
);

CREATE TABLE merchants (
    merchant_id   SERIAL PRIMARY KEY,
    name          VARCHAR(100) NOT NULL,
    category      VARCHAR(50),
    country       VARCHAR(2)
);

CREATE TABLE transactions (
    transaction_id SERIAL PRIMARY KEY,
    account_id     INT REFERENCES accounts(account_id),
    merchant_id    INT REFERENCES merchants(merchant_id),
    txn_type       VARCHAR(20) NOT NULL,
    amount         NUMERIC(12,2) NOT NULL,
    currency       VARCHAR(3) DEFAULT 'INR',
    status         VARCHAR(20) DEFAULT 'COMPLETED',
    channel        VARCHAR(20),
    device_id      VARCHAR(50),
    created_at     TIMESTAMP DEFAULT NOW()
);