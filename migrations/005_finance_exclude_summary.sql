-- مایگریشن مالی ۰۰۵: خارج کردن تراکنش از خلاصه
-- تاریخ: ۱۴۰۵/۰۷/۲۵ (2026-10-17)
--
-- چرا: دریافت وام درآمد نیست، بدهی است. اگر در income شمرده شود
-- گزارش درآمد کاربر چند صد میلیون بیشتر از واقعیت می‌شود.

ALTER TABLE finance.transactions
    ADD COLUMN IF NOT EXISTS exclude_from_summary boolean NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS ix_fin_tx_exclude
    ON finance.transactions(user_id, exclude_from_summary);
