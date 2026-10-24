-- بهوش — فاز صفر: احراز هویت چندکاربره
-- قاعده: هیچ‌چیز حذف نمی‌شود، فقط غیرفعال. توکن خام هرگز ذخیره نمی‌شود، فقط هش.
-- سازگاری: جدول users دست‌نخورده می‌ماند تا ثبت‌های سلامت قطع نشوند.

-- اعتبارنامه ورود. جدول جدا تا users فقط پروفایل بماند.
CREATE TABLE IF NOT EXISTS auth_credentials (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_login_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_auth_credentials_email ON auth_credentials (lower(email));

-- توکن‌های دسترسی. هم برای داشبورد، هم برای ایجنت‌های MCP.
-- جدول api_tokens قبلی استفاده نمی‌شد؛ این نسخه گسترش‌یافته همان است.
ALTER TABLE api_tokens ADD COLUMN IF NOT EXISTS name TEXT NOT NULL DEFAULT '';
ALTER TABLE api_tokens ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE api_tokens ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMPTZ;
ALTER TABLE api_tokens ADD COLUMN IF NOT EXISTS kind TEXT NOT NULL DEFAULT 'api';
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_tokens_hash ON api_tokens (token_hash);

-- اسکیمای مالی، جدا از سلامت. مدل دوبل‌انتری سبک.
CREATE SCHEMA IF NOT EXISTS finance;

CREATE TABLE IF NOT EXISTS finance.accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('asset','expense','income','liability')),
  currency TEXT NOT NULL DEFAULT 'IRT',
  card_last4 TEXT,
  opening_balance NUMERIC(18,2) NOT NULL DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_fin_accounts_user ON finance.accounts (user_id);

CREATE TABLE IF NOT EXISTS finance.categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('expense','income')),
  parent_id UUID REFERENCES finance.categories(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, name, kind)
);

CREATE TABLE IF NOT EXISTS finance.transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  occurred_at TIMESTAMPTZ NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  category_id UUID REFERENCES finance.categories(id) ON DELETE SET NULL,
  counterparty TEXT,
  source TEXT NOT NULL DEFAULT 'manual'
    CHECK (source IN ('manual','sms','csv','agent','import')),
  external_ref TEXT,
  raw_message_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fin_tx_user_date ON finance.transactions (user_id, occurred_at DESC);
-- کلید یکتا روی شماره پیگیری: جلوی ثبت دوباره یک پیامک را می‌گیرد.
CREATE UNIQUE INDEX IF NOT EXISTS idx_fin_tx_external_ref
  ON finance.transactions (user_id, external_ref) WHERE external_ref IS NOT NULL;

CREATE TABLE IF NOT EXISTS finance.entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  transaction_id UUID NOT NULL REFERENCES finance.transactions(id) ON DELETE CASCADE,
  account_id UUID NOT NULL REFERENCES finance.accounts(id) ON DELETE RESTRICT,
  amount NUMERIC(18,2) NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('debit','credit')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fin_entries_tx ON finance.entries (transaction_id);
CREATE INDEX IF NOT EXISTS idx_fin_entries_account ON finance.entries (account_id);

CREATE TABLE IF NOT EXISTS finance.budgets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category_id UUID NOT NULL REFERENCES finance.categories(id) ON DELETE CASCADE,
  period TEXT NOT NULL DEFAULT 'monthly' CHECK (period IN ('weekly','monthly','yearly')),
  amount NUMERIC(18,2) NOT NULL DEFAULT 0,
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, category_id, period)
);

-- پیامک خام بانک. منبع حقیقت. حتی اگر پارس شکست بخورد داده از دست نمی‌رود.
CREATE TABLE IF NOT EXISTS finance.raw_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel TEXT NOT NULL DEFAULT 'sms',
  bank TEXT,
  body TEXT NOT NULL,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  parsed BOOLEAN NOT NULL DEFAULT false,
  parse_error TEXT,
  transaction_id UUID REFERENCES finance.transactions(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_fin_raw_user ON finance.raw_messages (user_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_fin_raw_unparsed ON finance.raw_messages (user_id) WHERE parsed = false;

-- هر نوشتن ایجنت اینجا ثبت می‌شود. الگو از open-finance.
CREATE TABLE IF NOT EXISTS finance.audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  actor TEXT NOT NULL DEFAULT 'agent',
  token_id UUID,
  tool TEXT NOT NULL,
  payload JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fin_audit_user ON finance.audit_log (user_id, created_at DESC);
