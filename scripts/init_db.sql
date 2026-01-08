-- AML Transaction Intelligence Database Initialization
-- PostgreSQL with pgvector extension

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ===========================================
-- TRANSACTIONS TABLE (Raw cleaned data)
-- ===========================================
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL,
    from_bank VARCHAR(50),
    source_account VARCHAR(100) NOT NULL,
    to_bank VARCHAR(50),
    destination_account VARCHAR(100) NOT NULL,
    amount_received DECIMAL(18, 2),
    receiving_currency VARCHAR(20),
    amount_paid DECIMAL(18, 2),
    payment_currency VARCHAR(20),
    payment_format VARCHAR(50),
    is_laundering INTEGER DEFAULT 0,
    high_risk_outlier BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ===========================================
-- ALERTS TABLE (Suspicious activity)
-- ===========================================
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(100) NOT NULL,
    source_account VARCHAR(100) NOT NULL,
    transaction_count INTEGER,
    total_amount DECIMAL(18, 2),
    avg_amount DECIMAL(18, 2),
    window_start TIMESTAMP,
    window_end TIMESTAMP,
    risk_score DECIMAL(5, 2),
    status VARCHAR(50) DEFAULT 'NEW',
    explanation TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TIMESTAMP,
    reviewed_by VARCHAR(100)
);

-- ===========================================
-- REGULATORY_DOCS TABLE (RAG Vector Store)
-- ===========================================
CREATE TABLE IF NOT EXISTS regulatory_docs (
    id SERIAL PRIMARY KEY,
    document_name VARCHAR(255) NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),  -- nomic-embed-text dimension
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_regulatory_docs_embedding 
ON regulatory_docs USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- ===========================================
-- CASE_CACHE TABLE (Redis backup/audit)
-- ===========================================
CREATE TABLE IF NOT EXISTS case_cache (
    id SERIAL PRIMARY KEY,
    alert_id INTEGER REFERENCES alerts(id),
    cache_key VARCHAR(255) UNIQUE NOT NULL,
    explanation TEXT,
    prompt_version VARCHAR(50),
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);

-- ===========================================
-- INDEXES FOR PERFORMANCE
-- ===========================================
CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions(source_account);
CREATE INDEX IF NOT EXISTS idx_transactions_timestamp ON transactions(timestamp);
CREATE INDEX IF NOT EXISTS idx_transactions_laundering ON transactions(is_laundering);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_source ON alerts(source_account);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC);

-- ===========================================
-- MLFLOW TABLES (Auto-created by MLflow)
-- ===========================================
-- MLflow will auto-create its tables on first connection

-- Grant permissions (if needed)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO aml_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO aml_user;
