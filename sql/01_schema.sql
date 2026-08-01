-- 01_schema.sql

CREATE SCHEMA finsight;

-- ===== CREDIT RISK MODULE =====
CREATE TABLE finsight.loans (
    loan_id           BIGINT PRIMARY KEY,
    member_id         BIGINT,
    loan_amount       NUMERIC(12,2),
    funded_amount     NUMERIC(12,2),
    term_months       INT,
    interest_rate     NUMERIC(5,2),
    installment       NUMERIC(10,2),
    grade             CHAR(1),
    sub_grade         VARCHAR(3),
    employment_length VARCHAR(20),
    home_ownership    VARCHAR(20),
    annual_income     NUMERIC(14,2),
    verification_status VARCHAR(30),
    issue_date        DATE,
    loan_status       VARCHAR(30),       -- Fully Paid / Charged Off / Default / Current
    purpose           VARCHAR(50),
    dti               NUMERIC(6,2),      -- debt-to-income ratio
    delinq_2yrs       INT,
    fico_range_low    INT,
    fico_range_high   INT,
    open_accounts     INT,
    total_accounts    INT,
    revol_util        NUMERIC(6,2),
    state             VARCHAR(2)
);

-- ===== TRANSACTION / FRAUD MODULE =====
CREATE TABLE finsight.transactions (
    txn_id            BIGSERIAL PRIMARY KEY,
    step              INT,               -- time unit (1 step = 1 hour)
    txn_type          VARCHAR(20),       -- CASH_IN, CASH_OUT, TRANSFER, PAYMENT, DEBIT
    amount            NUMERIC(14,2),
    sender_id         VARCHAR(30),
    sender_bal_before NUMERIC(14,2),
    sender_bal_after  NUMERIC(14,2),
    receiver_id       VARCHAR(30),
    receiver_bal_before NUMERIC(14,2),
    receiver_bal_after  NUMERIC(14,2),
    is_fraud          SMALLINT,          -- ground truth label (from PaySim)
    is_flagged_rule   SMALLINT,          -- flagged by business rule engine
    anomaly_score     NUMERIC(10,6),     -- Isolation Forest decision_function, higher = more anomalous
    is_flagged_iforest SMALLINT          -- Isolation Forest flag, contamination matched to is_flagged_rule's rate
);

-- ===== MARKET DATA MODULE =====
CREATE TABLE finsight.stock_prices (
    price_id      BIGSERIAL PRIMARY KEY,
    ticker        VARCHAR(15),
    trade_date    DATE,
    open_price    NUMERIC(12,2),
    high_price    NUMERIC(12,2),
    low_price     NUMERIC(12,2),
    close_price   NUMERIC(12,2),
    adj_close     NUMERIC(12,2),
    volume        BIGINT,
    daily_return  NUMERIC(8,5)
);

-- ===== CUSTOMER DIMENSION (bridges loans + transactions for segmentation) =====
CREATE TABLE finsight.customers (
    customer_id     VARCHAR(30) PRIMARY KEY,
    signup_date     DATE,
    segment         VARCHAR(20),         -- filled in after RFM clustering
    total_txn_count INT,
    total_txn_value NUMERIC(14,2),
    avg_txn_value   NUMERIC(14,2),
    last_txn_date   DATE,
    risk_score      NUMERIC(5,2)
);

CREATE INDEX idx_loans_status ON finsight.loans(loan_status);
CREATE INDEX idx_txn_type ON finsight.transactions(txn_type);
CREATE INDEX idx_txn_fraud ON finsight.transactions(is_fraud);
CREATE INDEX idx_stock_ticker_date ON finsight.stock_prices(ticker, trade_date);
