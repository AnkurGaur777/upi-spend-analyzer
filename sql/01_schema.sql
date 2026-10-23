-- sql/01_schema.sql  (MySQL 8)
CREATE TABLE IF NOT EXISTS transactions (
  txn_id      VARCHAR(16)  PRIMARY KEY,
  txn_date    DATE         NOT NULL,
  txn_month   CHAR(7)      NOT NULL,
  weekday     VARCHAR(10),
  narration   VARCHAR(255),
  merchant    VARCHAR(100),
  amount      DECIMAL(12,2) NOT NULL,
  direction   ENUM('debit','credit') NOT NULL,
  balance     DECIMAL(14,2),
  category    VARCHAR(40),
  cat_method  VARCHAR(10),
  is_transfer TINYINT(1) DEFAULT 0,
  is_refund   TINYINT(1) DEFAULT 0,
  is_reversal TINYINT(1) DEFAULT 0,
  source_bank VARCHAR(30),
  INDEX idx_date (txn_date),
  INDEX idx_cat (category),
  INDEX idx_merchant (merchant)
);

CREATE TABLE IF NOT EXISTS recurring_payments (
  merchant       VARCHAR(100) PRIMARY KEY,
  category       VARCHAR(40),
  frequency      VARCHAR(12),
  typical_amount DECIMAL(12,2),
  n_payments     INT,
  first_seen     DATE,
  last_seen      DATE,
  annual_cost    DECIMAL(12,2)
);
