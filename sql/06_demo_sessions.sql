-- Additive session ledger for explicitly labelled, reproducible teaching demos.
CREATE TABLE IF NOT EXISTS retailpulse_demo_sessions (
    session_id TEXT PRIMARY KEY,
    idempotency_key VARCHAR(80) UNIQUE NOT NULL,
    label VARCHAR(160) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_order_codes JSONB NOT NULL,
    source_item_ids JSONB NOT NULL,
    baseline_global JSONB NOT NULL,
    expected JSONB NOT NULL,
    source_payload JSONB NOT NULL
);
COMMENT ON TABLE retailpulse_demo_sessions IS
    'Owned DEMO orders and expected KPIs; preparation is idempotent and never resets user data';
