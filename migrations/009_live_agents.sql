-- 009: دفترچه ایجنت‌های جلسه.
--
-- چرا لازم است: قبلا توکن ایجنت روی خود نشست می‌نشست، پس کاربر هر بار
-- مجبور بود توکن را دوباره بچسباند. حالا ایجنت‌ها یک بار با یک نام
-- ذخیره می‌شوند و در هر جلسه فقط انتخاب می‌شوند.
--
-- توکن خام ذخیره می‌شود چون برای فراخوانی AMP لازم است، ولی هرگز در
-- پاسخ API برنمی‌گردد. API فقط چهار کاراکتر آخر را نشان می‌دهد.
--
-- idempotent: اجرای دوباره خطا نمی‌دهد.

create table if not exists live.agents (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.users(id) on delete cascade,
  name        text not null,
  token       text not null,
  note        text,
  archived    boolean not null default false,
  token_ok    boolean,
  last_error  text,
  last_used_at timestamptz,
  created_at  timestamptz not null default now()
);

-- نام تکراری در یک حساب معنا ندارد. ولی ایجنت بایگانی‌شده نامش آزاد می‌شود.
create unique index if not exists ux_live_agents_user_name
  on live.agents (user_id, lower(name)) where archived = false;

create index if not exists ix_live_agents_user
  on live.agents (user_id, archived, created_at desc);

-- ---------- پیوند نشست و ایجنت ----------
-- یک نشست می‌تواند چند ایجنت داشته باشد و یک ایجنت در چند نشست باشد.
-- نشست AMP اینجا می‌نشیند نه روی ایجنت، چون توکن AMP به یک نشست قفل است
-- و دو جلسه همزمان با یک ایجنت نباید نشست همدیگر را خراب کنند.
create table if not exists live.session_agents (
  session_id uuid not null references live.sessions(id) on delete cascade,
  agent_id   uuid not null references live.agents(id) on delete cascade,
  amp_session_id text,
  joined_at  timestamptz not null default now(),
  primary key (session_id, agent_id)
);

create index if not exists ix_live_session_agents_agent
  on live.session_agents (agent_id);

-- ---------- بازه‌ها حالا به یک ایجنت مشخص تعلق دارند ----------
-- هر ارسال به هر ایجنت یک ردیف جدا می‌شود تا پاسخ هر کدام جدا بنشیند.
alter table live.segments add column if not exists agent_id uuid
  references live.agents(id) on delete set null;

-- نام ایجنت به‌صورت عکس فوری. اگر ایجنت بعدا پاک شود، تاریخچه بی‌نام نمی‌ماند.
alter table live.segments add column if not exists agent_name text;

comment on column live.segments.agent_id is
  'ایجنت گیرنده این بازه. خالی یعنی نشست قدیمی تک‌ایجنت یا ارسال بدون ایجنت.';
comment on column live.agents.token is
  'توکن AMP. هرگز در پاسخ API برنمی‌گردد.';

create index if not exists ix_live_segments_pending_reply_v2
  on live.segments (session_id, agent_id)
  where agent_reply is null and amp_msg_id is not null;

-- ---------- نشانگر ارسال، برای هر ایجنت جدا ----------
-- نشانگر روی نشست کافی نیست. اگر به دو ایجنت بفرستیم و یکی خطا بدهد،
-- نشانگر نشست جلو نمی‌رود و ایجنت موفق متن تکراری می‌گیرد. پس هر پیوند
-- نشانگر خودش را دارد.
alter table live.session_agents add column if not exists last_sent_seq integer not null default -1;
alter table live.session_agents add column if not exists last_sent_at timestamptz;

comment on column live.session_agents.last_sent_seq is
  'آخرین تکه ارسال‌شده به این ایجنت در این نشست. منفی یک یعنی هیچ‌چیز.';
