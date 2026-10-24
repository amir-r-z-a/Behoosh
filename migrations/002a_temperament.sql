-- مهاجرت ۰۰۲: مزاج دو محوره روی وعده‌ها + جدول بردار پایه
ALTER TABLE meals
  ADD COLUMN IF NOT EXISTS cold_warm NUMERIC(4,3) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS dry_wet   NUMERIC(4,3) NOT NULL DEFAULT 0;

-- جدول بردار پایه اقلام (غذا/رفتار/مداخله)
CREATE TABLE IF NOT EXISTS temperament_vectors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item_name TEXT NOT NULL,
  item_type TEXT NOT NULL CHECK (item_type IN ('food','behavior','intervention')),
  cold_warm NUMERIC(3,2) NOT NULL DEFAULT 0,
  dry_wet   NUMERIC(3,2) NOT NULL DEFAULT 0,
  max_weight NUMERIC NOT NULL DEFAULT 1,
  decay_lambda NUMERIC NOT NULL DEFAULT 0.1,
  source_ref TEXT,
  verified BOOLEAN NOT NULL DEFAULT false,
  UNIQUE (item_name, item_type));

-- جدول حالت مزاج روزانه
CREATE TABLE IF NOT EXISTS temperament_state (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL,
  cold_warm NUMERIC(4,3) NOT NULL DEFAULT 0,
  dry_wet   NUMERIC(4,3) NOT NULL DEFAULT 0,
  computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, log_date));

-- چند بردار پایه نمونه (تأییدنشده؛ فقط برای راه‌اندازی)
INSERT INTO temperament_vectors (item_name, item_type, cold_warm, dry_wet, source_ref, verified) VALUES
  ('خرما','food', 0.60, 0.30, 'seed/unsourced', false),
  ('عسل','food', 0.55, 0.20, 'seed/unsourced', false),
  ('ماست','food', -0.40, -0.50, 'seed/unsourced', false),
  ('خیار','food', -0.50, -0.40, 'seed/unsourced', false),
  ('گوشت گوسفند','food', 0.60, 0.40, 'seed/unsourced', false),
  ('مرغ','food', 0.20, 0.10, 'seed/unsourced', false),
  ('ماهی','food', 0.10, -0.30, 'seed/unsourced', false),
  ('برنج','food', 0.10, 0.20, 'seed/unsourced', false),
  ('نان گندم','food', 0.20, 0.40, 'seed/unsourced', false),
  ('چای','food', 0.30, 0.60, 'seed/unsourced', false),
  ('قهوه','food', 0.50, 0.70, 'seed/unsourced', false),
  ('بادام','food', 0.30, 0.50, 'seed/unsourced', false),
  ('گردو','food', 0.40, 0.60, 'seed/unsourced', false),
  ('کاهو','food', -0.40, -0.20, 'seed/unsourced', false),
  ('سکنجبین','food', -0.30, -0.20, 'seed/unsourced', false),
  ('بابونه','food', -0.20, -0.10, 'seed/unsourced', false)
ON CONFLICT (item_name, item_type) DO NOTHING;
