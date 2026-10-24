-- 006: دستیار جلسه زنده (بهوش جلسه)
-- اسکیمای live جدا از public و finance. اگر این ماژول خراب شود، بقیه دست‌نخورده می‌ماند.
-- همه اعداد آستانه از سند طراحی behoosh-live-meeting-design.html آمده‌اند.

create schema if not exists live;

-- ---------- نشست‌ها ----------
create table if not exists live.sessions (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references public.users(id) on delete cascade,
  title               text,
  started_at          timestamptz not null default now(),
  ended_at            timestamptz,
  status              text not null default 'recording',   -- recording | stopped | failed
  asr_provider        text not null default 'sina',
  diarize             boolean not null default false,
  -- آستانه‌ها: هر کدام اول رسید، ارسال انجام می‌شود
  word_threshold      integer not null default 400,
  time_threshold_s    integer not null default 90,
  silence_threshold_s integer not null default 6,
  min_words_to_send   integer not null default 60,
  -- شمارنده‌ها
  total_words         integer not null default 0,
  last_sent_seq       integer not null default 0,
  last_sent_at        timestamptz,
  -- پل ایجنت. توکن هرگز در پاسخ API برنمی‌گردد.
  agent_token         text,
  agent_label         text,
  amp_session_id      text,
  created_at          timestamptz not null default now()
);

-- ---------- تکه‌های صدا ----------
create table if not exists live.chunks (
  id          bigserial primary key,
  session_id  uuid not null references live.sessions(id) on delete cascade,
  seq         integer not null,
  start_s     numeric not null,
  end_s       numeric not null,
  bytes       integer,
  silence     boolean not null default false,
  status      text not null default 'pending',   -- pending | running | done | error
  asr_job_id  text,
  text        text,
  words       integer not null default 0,
  error       text,
  created_at  timestamptz not null default now(),
  unique (session_id, seq)
);

-- ---------- بازه‌های ارسالی به ایجنت ----------
create table if not exists live.segments (
  id            bigserial primary key,
  session_id    uuid not null references live.sessions(id) on delete cascade,
  from_seq      integer not null,
  to_seq        integer not null,
  from_s        numeric not null,
  to_s          numeric not null,
  text          text not null,
  words         integer not null,
  trigger       text not null,                   -- words | time | silence | manual
  sent_to_agent boolean not null default false,
  send_error    text,
  agent_reply   text,
  created_at    timestamptz not null default now()
);

create index if not exists live_chunks_session_seq on live.chunks (session_id, seq);
create index if not exists live_segments_session_created on live.segments (session_id, created_at);
create index if not exists live_sessions_user_started on live.sessions (user_id, started_at desc);
