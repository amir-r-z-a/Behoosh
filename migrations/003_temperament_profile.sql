-- مهاجرت ۰۰۳: مزاج پایه و معاینه ارگان‌ها
-- مزاج پایه = نقطه لنگر کاربر روی صفحه دو محوره (از پرسشنامه + معاینه)
-- معاینه ارگان‌ها = بردار مزاج هر عضو (قلب، کبد، معده، ...) برای تشخیص اولیه

CREATE TABLE IF NOT EXISTS temperament_profile (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  base_cold_warm NUMERIC(4,3) NOT NULL DEFAULT 0,   -- -1..1
  base_dry_wet   NUMERIC(4,3) NOT NULL DEFAULT 0,
  constitution TEXT,                                 -- سوداوی، صفراوی، دموی، بلغمی، مرکب
  method TEXT NOT NULL DEFAULT 'hybrid',             -- modern|traditional|hybrid
  note TEXT,
  calibrated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id));

-- معاینه ارگان‌ها: هر عضو یک بردار سردی/گرمی و خشکی/تری دارد
CREATE TABLE IF NOT EXISTS temperament_exam (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  organ TEXT NOT NULL,          -- heart, liver, stomach, brain, kidney, lung, intestine, uterus, ...
  cold_warm NUMERIC(4,3) NOT NULL DEFAULT 0,
  dry_wet   NUMERIC(4,3) NOT NULL DEFAULT 0,
  severity  SMALLINT NOT NULL DEFAULT 0,   -- ۰ تا ۳ (درجه)
  finding   TEXT,               -- یافته معاینه/علامت
  source    TEXT NOT NULL DEFAULT 'agent',
  measured_at DATE NOT NULL,
  UNIQUE (user_id, organ));
