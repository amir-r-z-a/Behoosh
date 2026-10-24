-- 008: شناسه پیام AMP برای وصل کردن پاسخ ایجنت به بازه درست.
--
-- چرا لازم است: ارسال به ایجنت غیرهمگام است. پاسخ ایجنت با فیلد reply_to
-- به شناسه پیام ما برمی‌گردد. بدون ذخیره این شناسه، نمی‌فهمیدیم کدام پاسخ
-- مربوط به کدام بازه است و پاسخ‌ها بی‌صاحب می‌ماندند.
--
-- idempotent: اجرای دوباره خطا نمی‌دهد.

ALTER TABLE live.segments ADD COLUMN IF NOT EXISTS amp_msg_id text;

COMMENT ON COLUMN live.segments.amp_msg_id IS
  'شناسه پیام ارسالی در کانال AMP. کلید وصل کردن پاسخ ایجنت به این بازه.';

-- نمایه برای جستجوی بازه‌های بی‌پاسخ
CREATE INDEX IF NOT EXISTS ix_live_segments_pending_reply
  ON live.segments (session_id)
  WHERE agent_reply IS NULL AND amp_msg_id IS NOT NULL;
