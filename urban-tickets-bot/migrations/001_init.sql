CREATE TABLE IF NOT EXISTS users (
  id BIGSERIAL PRIMARY KEY,
  tg_id BIGINT UNIQUE NOT NULL,
  username TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS requisites (
  id BIGSERIAL PRIMARY KEY,
  bank TEXT NOT NULL,
  holder TEXT NOT NULL,
  account TEXT NOT NULL,
  comment TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT FALSE,
  usage_count INT NOT NULL DEFAULT 0,
  order_idx INT NOT NULL
);

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_status') THEN
    CREATE TYPE payment_status AS ENUM ('pending','confirmed','rejected');
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS payments (
  id BIGSERIAL PRIMARY KEY,
  user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  requisites_id BIGINT NOT NULL REFERENCES requisites(id),
  amount INT NOT NULL,
  file_id TEXT NOT NULL,
  file_type TEXT NOT NULL, -- 'photo' | 'document'
  batch_counter INT NOT NULL, -- 1..20
  status payment_status NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fsm_states (
  user_tg_id BIGINT PRIMARY KEY,
  state TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
