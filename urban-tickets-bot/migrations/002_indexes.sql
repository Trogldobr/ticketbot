CREATE INDEX IF NOT EXISTS idx_requisites_active ON requisites(active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_requisites_order_idx ON requisites(order_idx);
CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_requisites_id ON payments(requisites_id);
