CREATE TABLE IF NOT EXISTS price_logs (
    id serial PRIMARY KEY,
    crypto_name VARCHAR(50) NOT NULL,
    current_price NUMERIC (18,8) NOT NULL,
    sma_value NUMERIC (18,8),
    deviation_percent NUMERIC(8,4),
    time_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_asset_name ON price_logs (crypto_name , time_created DESC);