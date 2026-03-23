ALTER TABLE payments
  ADD COLUMN IF NOT EXISTS ticket_full_name TEXT;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_name='payments' AND column_name='full_name'
  ) THEN
    UPDATE payments
    SET ticket_full_name = COALESCE(ticket_full_name, full_name);
  END IF;
END$$;

-- 3) удаляю устаревшую колонку (если была)
ALTER TABLE payments
  DROP COLUMN IF EXISTS full_name;


