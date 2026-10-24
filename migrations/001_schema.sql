-- gen_random_uuid() در هسته پستگرس ۱۳ به بالا موجود است. pgcrypto فقط
-- برای نسخه‌های قدیمی‌تر لازم است، پس نبودنش نباید مایگریشن را بشکند.
DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS pgcrypto;
EXCEPTION WHEN OTHERS THEN
  RAISE NOTICE 'pgcrypto در دسترس نیست؛ از gen_random_uuid هسته استفاده می‌شود';
END $$;

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  display_name TEXT NOT NULL, birth_date DATE, gender TEXT, height_cm NUMERIC(5,1),
  timezone TEXT NOT NULL DEFAULT 'Asia/Tehran', language TEXT NOT NULL DEFAULT 'fa',
  method TEXT NOT NULL DEFAULT 'hybrid' CHECK (method IN ('modern','traditional','hybrid')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS goals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  goal_type TEXT NOT NULL, target_value NUMERIC NOT NULL DEFAULT 0,
  target_unit TEXT NOT NULL DEFAULT '', active BOOLEAN NOT NULL DEFAULT true,
  UNIQUE (user_id, goal_type));

CREATE TABLE IF NOT EXISTS baseline (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL, measured_at DATE NOT NULL, payload JSONB NOT NULL DEFAULT '{}',
  source_file_url TEXT, UNIQUE (user_id, kind, measured_at));

CREATE TABLE IF NOT EXISTS meals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL, slot TEXT NOT NULL, item_name TEXT NOT NULL,
  quantity NUMERIC NOT NULL DEFAULT 0, unit TEXT NOT NULL DEFAULT 'gram',
  kcal NUMERIC NOT NULL DEFAULT 0, protein_g NUMERIC NOT NULL DEFAULT 0,
  carbs_g NUMERIC NOT NULL DEFAULT 0, fat_g NUMERIC NOT NULL DEFAULT 0,
  source TEXT NOT NULL DEFAULT 'agent' CHECK (source IN ('user','db','agent')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_meals_date ON meals(user_id, log_date);

CREATE TABLE IF NOT EXISTS workouts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL, kind TEXT NOT NULL, start_time TIMESTAMPTZ, end_time TIMESTAMPTZ,
  duration_min INT NOT NULL DEFAULT 0, kcal_burned NUMERIC NOT NULL DEFAULT 0,
  muscles TEXT[] NOT NULL DEFAULT '{}', notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS idx_workouts_date ON workouts(user_id, log_date);

CREATE TABLE IF NOT EXISTS workout_sets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workout_id UUID NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
  exercise TEXT NOT NULL, muscle_group TEXT, sets INT NOT NULL DEFAULT 0,
  reps INT NOT NULL DEFAULT 0, weight_kg NUMERIC NOT NULL DEFAULT 0);

CREATE TABLE IF NOT EXISTS sleep_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL, bedtime TIMESTAMPTZ, wake_time TIMESTAMPTZ,
  main_hours NUMERIC(4,1) NOT NULL DEFAULT 0, nap_min INT NOT NULL DEFAULT 0,
  quality SMALLINT NOT NULL DEFAULT 0 CHECK (quality BETWEEN 0 AND 10),
  wake_count INT NOT NULL DEFAULT 0, note TEXT, UNIQUE (user_id, log_date));

CREATE TABLE IF NOT EXISTS body_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  measured_at DATE NOT NULL, weight_kg NUMERIC(5,2) NOT NULL DEFAULT 0,
  body_fat_pct NUMERIC(4,1) NOT NULL DEFAULT 0, visceral_fat NUMERIC(4,1) NOT NULL DEFAULT 0,
  muscle_kg NUMERIC(5,2) NOT NULL DEFAULT 0, muscle_pct NUMERIC(4,1) NOT NULL DEFAULT 0,
  water_pct NUMERIC(4,1) NOT NULL DEFAULT 0, bmi NUMERIC(4,1) NOT NULL DEFAULT 0,
  labs JSONB NOT NULL DEFAULT '{}', UNIQUE (user_id, measured_at));

CREATE TABLE IF NOT EXISTS prayers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL,
  prayer TEXT NOT NULL CHECK (prayer IN ('fajr','dhuhr','asr','maghrib','isha')),
  status TEXT NOT NULL CHECK (status IN ('done','late','qada','missed')),
  UNIQUE (user_id, log_date, prayer));

CREATE TABLE IF NOT EXISTS mood_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL,
  mood SMALLINT NOT NULL DEFAULT 0 CHECK (mood BETWEEN 0 AND 10),
  stress SMALLINT NOT NULL DEFAULT 0 CHECK (stress BETWEEN 0 AND 10),
  energy SMALLINT NOT NULL DEFAULT 0 CHECK (energy BETWEEN 0 AND 10),
  symptoms JSONB NOT NULL DEFAULT '{}', note TEXT, UNIQUE (user_id, log_date));

CREATE TABLE IF NOT EXISTS screen_time (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL, total_min INT NOT NULL DEFAULT 0,
  instagram_min INT NOT NULL DEFAULT 0, telegram_min INT NOT NULL DEFAULT 0,
  other_min INT NOT NULL DEFAULT 0, unlocks INT NOT NULL DEFAULT 0,
  notifications INT NOT NULL DEFAULT 0, UNIQUE (user_id, log_date));

CREATE TABLE IF NOT EXISTS habits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL, breathing_done BOOLEAN NOT NULL DEFAULT false,
  water_liters NUMERIC(3,1) NOT NULL DEFAULT 0,
  supplements JSONB NOT NULL DEFAULT '[]', teas JSONB NOT NULL DEFAULT '[]',
  interventions JSONB NOT NULL DEFAULT '[]', UNIQUE (user_id, log_date));

CREATE TABLE IF NOT EXISTS temperament_vectors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item_name TEXT NOT NULL,
  item_type TEXT NOT NULL CHECK (item_type IN ('food','behavior','intervention')),
  cold_warm NUMERIC(3,2) NOT NULL DEFAULT 0, dry_wet NUMERIC(3,2) NOT NULL DEFAULT 0,
  max_weight NUMERIC NOT NULL DEFAULT 1, decay_lambda NUMERIC NOT NULL DEFAULT 0.1,
  source_ref TEXT, verified BOOLEAN NOT NULL DEFAULT false,
  UNIQUE (item_name, item_type));

CREATE TABLE IF NOT EXISTS temperament_state (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  log_date DATE NOT NULL, cold_warm NUMERIC(4,3) NOT NULL DEFAULT 0,
  dry_wet NUMERIC(4,3) NOT NULL DEFAULT 0, computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, log_date));

CREATE TABLE IF NOT EXISTS raw_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel TEXT NOT NULL DEFAULT 'telegram', received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  body TEXT NOT NULL, parsed BOOLEAN NOT NULL DEFAULT false);

CREATE TABLE IF NOT EXISTS api_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL, scopes JSONB NOT NULL DEFAULT '[]',
  revoked BOOLEAN NOT NULL DEFAULT false, created_at TIMESTAMPTZ NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS units (
  code TEXT PRIMARY KEY, label_fa TEXT NOT NULL, grams_per_unit NUMERIC);

INSERT INTO units (code, label_fa, grams_per_unit) VALUES
  ('gram','گرم',1),('spoon','قاشق',15),('piece','عدد',NULL),
  ('glass','لیوان',240),('palm','کف دست',NULL),('bowl','پیاله',150)
ON CONFLICT (code) DO NOTHING;
