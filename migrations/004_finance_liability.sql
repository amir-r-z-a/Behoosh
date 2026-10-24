-- مایگریشن مالی ۰۰۴: مدل بدهی، انتقال داخلی
-- تاریخ: ۱۴۰۵/۰۷/۲۵ (2026-10-17)
--
-- چرا: وام و قسط قبلا فقط هزینه ثبت می‌شد و اصل بدهی و مانده گم می‌شد.
-- با این جدول، اصل وام بدهی است نه درآمد، و هر قسط به وامش وصل می‌شود.

CREATE SCHEMA IF NOT EXISTS finance;

-- ---------- ۱. بدهی و تعهد ----------
CREATE TABLE IF NOT EXISTS finance.liabilities (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name                text NOT NULL,
    kind                text NOT NULL DEFAULT 'loan',
    principal           numeric(18,2) NOT NULL DEFAULT 0,
    interest_rate       numeric(6,3)  NOT NULL DEFAULT 0,
    installments_total  integer       NOT NULL DEFAULT 0,
    installment_amount  numeric(18,2) NOT NULL DEFAULT 0,
    start_date          date          NOT NULL,
    due_day             integer,
    account_id          uuid REFERENCES finance.accounts(id) ON DELETE SET NULL,
    status              text NOT NULL DEFAULT 'active',
    note                text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS ix_fin_liab_user ON finance.liabilities(user_id, status);

-- ---------- ۲. اتصال تراکنش به بدهی + انتقال داخلی ----------
ALTER TABLE finance.transactions
    ADD COLUMN IF NOT EXISTS liability_id uuid
        REFERENCES finance.liabilities(id) ON DELETE SET NULL;

ALTER TABLE finance.transactions
    ADD COLUMN IF NOT EXISTS is_transfer boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS ix_fin_tx_liability ON finance.transactions(liability_id);
CREATE INDEX IF NOT EXISTS ix_fin_tx_transfer  ON finance.transactions(user_id, is_transfer);
